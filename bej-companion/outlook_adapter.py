"""Personal Outlook integration: read calendars, approve exact Bej task writes.

OAuth cache is stored only through the injected OS credential store. Disk state
contains private calendar IDs and busy times, never bearer or refresh tokens.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
import threading
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit

import msal
import requests

GRAPH = 'https://graph.microsoft.com/v1.0'
SCOPES = ['Calendars.ReadWrite']
MANILA = timezone(timedelta(hours=8))
FRESH_SECONDS = 900


class OutlookAdapter:
    def __init__(self, local_dir: Path, credential_store, *, http=None, app_factory=None):
        self.folder = Path(local_dir)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / 'outlook-state.json'
        self.store = credential_store
        self.http = http or requests.Session()
        self.http.trust_env = False
        self.factory = app_factory or msal.PublicClientApplication
        self.lock = threading.RLock()
        self.app = None
        self.cache = None
        self.pending = False
        self.error = None
        self.authenticated = False
        self.generation = 0
        self.previews = {}
        self.verified_recoveries = set()
        try:
            self.state = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(self.state, dict): raise ValueError()
        except FileNotFoundError:
            self.state = {}
        except (OSError, ValueError):
            raise ValueError('Outlook local state cannot be read safely.') from None

    def _save(self):
        descriptor, temporary = tempfile.mkstemp(prefix='.outlook-', dir=self.folder)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
                json.dump(self.state, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def _cache_key(self):
        return 'bej-outlook-msal-' + self.state['clientId']

    def _application(self):
        if not self.state.get('clientId'):
            raise ValueError('Configure a Microsoft application client ID first.')
        if self.app is None:
            try:
                cache = msal.SerializableTokenCache()
                stored = self.store.get(self._cache_key())
                if stored: cache.deserialize(stored)
                session = requests.Session()
                session.trust_env = False
                self.app = self.factory(self.state['clientId'],
                    authority='https://login.microsoftonline.com/consumers',
                    token_cache=cache, http_client=session)
                self.cache = cache
            except Exception:
                raise ValueError('Microsoft authentication could not be initialized.') from None
        return self.app

    def _persist_cache(self):
        if self.cache is not None and self.cache.has_state_changed:
            self.store.set(self._cache_key(), self.cache.serialize())

    def configure(self, client_id: str) -> dict:
        try: client_id = str(uuid.UUID(client_id.strip()))
        except (ValueError, AttributeError, TypeError):
            raise ValueError('Enter a valid Microsoft application client ID.') from None
        with self.lock:
            if client_id != self.state.get('clientId'):
                if self.state.get('clientId'): self.store.set(self._cache_key(), '')
                self.generation += 1
                self.pending = False
                self.app = self.cache = None
                self.previews.clear()
                self.state = {'clientId': client_id}
                self.error = None
                self.authenticated = False
                self._save()
            return self.status()

    def begin_login(self) -> dict:
        with self.lock:
            if self.pending: raise ValueError('A Microsoft sign-in is already pending.')
            app = self._application()
            try:
                flow = app.initiate_device_flow(scopes=SCOPES)
                safe = {key: flow[key] for key in ('user_code', 'verification_uri', 'expires_in')}
                parsed = urlsplit(safe['verification_uri'])
                if parsed.scheme != 'https' or parsed.hostname not in ('microsoft.com', 'www.microsoft.com', 'login.microsoftonline.com'):
                    raise ValueError()
            except Exception:
                raise ValueError('Microsoft sign-in could not be started.') from None
            self.pending, self.error = True, None
            generation = self.generation

            def poll():
                try:
                    result = app.acquire_token_by_device_flow(flow)
                    with self.lock:
                        if generation != self.generation: return
                        if not result.get('access_token'): raise ValueError()
                        self._persist_cache()
                        self._bind_account(app)
                        self.authenticated = True
                        self.error = None
                except Exception:
                    with self.lock:
                        if generation == self.generation:
                            self.error = 'Microsoft sign-in did not complete. Try connecting again.'
                finally:
                    with self.lock:
                        if generation == self.generation: self.pending = False

            threading.Thread(target=poll, daemon=True, name='bej-outlook-login').start()
            return safe

    def _bind_account(self, app):
        accounts = app.get_accounts()
        if len(accounts) != 1: raise ValueError('Connect exactly one personal Microsoft account.')
        identity = accounts[0].get('home_account_id')
        if not identity: raise ValueError('Microsoft account identity is unavailable.')
        if self.state.get('accountId') != identity:
            self.state = {'clientId': self.state['clientId'], 'accountId': identity}
            self.previews.clear()
            self._save()
        return accounts[0]

    def _token(self):
        try:
            app = self._application()
            account = self._bind_account(app)
            result = app.acquire_token_silent(SCOPES, account=account)
            self._persist_cache()
            if not result or not result.get('access_token'): raise ValueError()
            self.authenticated = True
            return result['access_token']
        except Exception:
            self.authenticated = False
            raise ValueError('Microsoft is disconnected. Connect your personal account again.') from None

    def status(self) -> dict:
        with self.lock:
            return {'configured': bool(self.state.get('clientId')), 'clientId': self.state.get('clientId', ''),
                    'connected': self.authenticated, 'authPending': self.pending, 'error': self.error,
                    'calendarId': self.state.get('calendarId'), 'lastSyncedAt': self.state.get('lastSyncedAt')}

    def _request(self, method, path, *, body=None, etag=None):
        url = path if path.startswith('https://') else GRAPH + path
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.netloc != 'graph.microsoft.com'
                or not parsed.path.startswith('/v1.0/') or parsed.fragment):
            raise ValueError('Microsoft returned an unsafe page URL.')
        headers = {'Authorization': 'Bearer ' + self._token(), 'Prefer': 'outlook.timezone="UTC"', 'Accept': 'application/json'}
        if etag: headers['If-Match'] = etag
        try:
            response = self.http.request(method, url, headers=headers, json=body,
                                         timeout=30, allow_redirects=False)
            if response.status_code not in (200, 201):
                raise ValueError()
            return response.json()
        except Exception:
            raise ValueError('Microsoft request failed; refresh or reconnect before retrying.') from None

    def _pages(self, path):
        seen = set()
        while path:
            if path in seen or len(seen) >= 1000: raise ValueError('Microsoft pagination did not complete.')
            seen.add(path)
            page = self._request('GET', path)
            if not isinstance(page.get('value'), list): raise ValueError('Microsoft returned an invalid calendar page.')
            yield from page['value']
            path = page.get('@odata.nextLink')

    def _calendars(self):
        calendars = list(self._pages('/me/calendars'))
        matches = [c for c in calendars if c.get('name', '').strip().casefold() == 'bej']
        if len(matches) > 1: raise ValueError('Multiple Bej calendars exist. Resolve duplicate names before syncing.')
        known = self.state.get('calendarId')
        if known and (not matches or matches[0]['id'] != known):
            raise ValueError('The connected Bej calendar changed. Reconnect before writing.')
        if not matches:
            created = self._request('POST', '/me/calendars', body={'name': 'Bej'})
            if not created.get('id'): raise ValueError('Microsoft did not confirm the Bej calendar.')
            matches = [created]
            calendars.append(created)
        self.state['calendarId'] = matches[0]['id']
        self._save()
        return calendars

    @staticmethod
    def _event_time(value):
        text = value['dateTime']
        # Graph returns up to seven fractional digits, accepted by fromisoformat.
        parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            zone = value.get('timeZone', 'UTC')
            if zone not in ('UTC', 'Etc/UTC'): raise ValueError('Unexpected Outlook event timezone.')
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(MANILA).isoformat()

    def cached_busy(self, day: str) -> dict:
        date.fromisoformat(day)
        with self.lock:
            entry = self.state.get('days', {}).get(day)
            if not entry: return {'busy': [], 'stale': True, 'lastSyncedAt': None}
            return {'busy': copy.deepcopy(entry['busy']),
                    'stale': bool(entry.get('failed')) or time.time() - entry['timestamp'] > FRESH_SECONDS,
                    'lastSyncedAt': entry['lastSyncedAt']}

    def _reconcile_creations(self, events):
        """Recover only transactions reserved on disk before an approved POST."""
        recovered = {}
        calendar = self.state['calendarId']
        for key, owned in self.state.get('owned', {}).items():
            if (owned.get('calendarId') != calendar or not owned.get('transactionId')
                    or not owned.get('snapshot')
                    or (owned.get('eventId') and not owned.get('recovered'))):
                continue
            matches = [event for event in events if event.get('transactionId') == owned['transactionId']]
            if not matches:
                continue
            if len(matches) != 1:
                raise ValueError('An unconfirmed Outlook transaction has multiple matching events. No tasks were written.')
            event = matches[0]
            candidate = {'kind': 'create', 'key': key, 'calendarId': calendar,
                         'title': event.get('subject'), 'start': self._event_time(event['start']),
                         'end': self._event_time(event['end'])}
            fingerprint = hashlib.sha256(json.dumps(candidate, sort_keys=True).encode()).hexdigest()
            if (fingerprint != owned['snapshot'] or event.get('attendees')
                    or event.get('isCancelled') or not event.get('id')
                    or not event.get('@odata.etag') or event.get('body', {}).get('content', '').strip()
                    or (owned.get('eventId') and owned['eventId'] != event['id'])):
                raise ValueError('An unconfirmed Outlook event differs from its approved task. No tasks were written.')
            recovered[key] = {**owned, 'eventId': event['id'], 'etag': event['@odata.etag'], 'recovered': True}
        # Apply only after every candidate validates; never appropriate partial matches.
        self.state.setdefault('owned', {}).update(recovered)
        return set(recovered)

    def sync(self, day: str) -> dict:
        selected = date.fromisoformat(day)
        with self.lock:
            self.verified_recoveries = set()
            try:
                self._token()
                calendars = self._calendars()
                start = datetime.combine(selected, datetime.min.time(), MANILA)
                end = start + timedelta(days=1)
                query = ('?startDateTime=' + quote(start.isoformat(), safe='')
                         + '&endDateTime=' + quote(end.isoformat(), safe='')
                         + '&$select=id,subject,start,end,showAs,isCancelled,transactionId,attendees,body')
                busy, bej_events = [], []
                for calendar in calendars:
                    path = '/me/calendars/' + quote(calendar['id'], safe='') + '/calendarView' + query
                    for event in self._pages(path):
                        if calendar['id'] == self.state['calendarId']: bej_events.append(event)
                        if event.get('isCancelled') or event.get('showAs') == 'free': continue
                        busy.append({'start': self._event_time(event['start']), 'end': self._event_time(event['end']),
                                     'eventId': event['id'], 'calendarId': calendar['id'], 'hasAttendees': bool(event.get('attendees'))})
                self.verified_recoveries = self._reconcile_creations(bej_events)
                timestamp = datetime.now(timezone.utc).isoformat()
                self.state.setdefault('days', {})[day] = {'busy': busy, 'timestamp': time.time(), 'lastSyncedAt': timestamp}
                self.state['lastSyncedAt'] = timestamp
                self.error = None
                self._save()
                return self.cached_busy(day)
            except Exception as error:
                # Only our fixed diagnostics are exposed; arbitrary transport errors may contain credentials.
                self.error = str(error) if isinstance(error, ValueError) else 'Outlook sync failed. Cached events may be incomplete.'
                entry = self.state.get('days', {}).get(day)
                if entry: entry['failed'] = True
                self._save()
                result = self.cached_busy(day)
                result.update(stale=True, error=self.error)
                return result

    def planning_busy(self, day: str, task_ids: list[str]) -> dict:
        """Allow a new local proposal to retain/move its own unshared task events."""
        with self.lock:
            result = self.cached_busy(day)
            owned_events = set()
            for identity in task_ids:
                key = hashlib.sha256((day + '\0' + identity).encode()).hexdigest()
                owned = self.state.get('owned', {}).get(key, {})
                if owned.get('eventId') and owned.get('calendarId') == self.state.get('calendarId'):
                    owned_events.add((owned['calendarId'], owned['eventId']))
            result['busy'] = [event for event in result['busy']
                              if event.get('hasAttendees', True) or (event.get('calendarId'), event.get('eventId')) not in owned_events]
            return result

    def _event_path(self, calendar, event=None):
        path = '/me/calendars/' + quote(calendar, safe='') + '/events'
        return path + '/' + quote(event, safe='') if event else path

    @staticmethod
    def _check_availability(operations, busy):
        def overlaps(first, second):
            try:
                return (datetime.fromisoformat(first['start']) < datetime.fromisoformat(second['end'])
                        and datetime.fromisoformat(second['start']) < datetime.fromisoformat(first['end']))
            except (KeyError, TypeError, ValueError):
                raise ValueError('Calendar availability is invalid. Sync this day again.') from None

        dependencies = {operation['key']: set() for operation in operations}
        moving = {(operation['calendarId'], operation['eventId']): operation
                  for operation in operations if operation['kind'] == 'update'}
        for index, operation in enumerate(operations):
            if any(overlaps(operation, other) for other in operations[index + 1:]):
                raise ValueError('The proposed task times overlap each other. Regenerate the plan before approving.')
        for operation in operations:
            for event in busy:
                if (operation['kind'] == 'update'
                        and event.get('calendarId') == operation['calendarId']
                        and event.get('eventId') == operation['eventId']):
                    continue
                if not overlaps(operation, event): continue
                predecessor = moving.get((event.get('calendarId'), event.get('eventId')))
                if predecessor and not event.get('hasAttendees', False):
                    dependencies[operation['key']].add(predecessor['key'])
                    continue
                raise ValueError('A task overlaps an Outlook busy event. Sync and regenerate the plan before approving.')
        ordered, resolved = [], set()
        while len(ordered) < len(operations):
            ready = [operation for operation in operations
                     if operation['key'] not in resolved and dependencies[operation['key']] <= resolved]
            if not ready:
                raise ValueError('These task moves form a cycle. Move tasks into free times using separate approvals first.')
            ordered.extend(ready)
            resolved.update(operation['key'] for operation in ready)
        return ordered, dependencies

    def preview(self, plan: dict) -> dict:
        with self.lock:
            self._token()
            try:
                day = date.fromisoformat(plan['date']).isoformat()
                if not isinstance(plan['id'], str) or not plan['id']: raise ValueError()
                blocks = plan['blocks']
                if not isinstance(blocks, list) or len(blocks) > 200: raise ValueError()
            except (KeyError, TypeError, ValueError): raise ValueError('The plan is invalid.') from None
            if self.cached_busy(day)['stale'] or not self.state.get('calendarId'):
                raise ValueError('Sync this day successfully before previewing Outlook changes.')
            operations, ids = [], set()
            calendar = self.state['calendarId']
            for block in blocks:
                try:
                    identity, title = block['id'], block['title']
                    if not isinstance(identity, str) or not identity or identity in ids: raise ValueError()
                    if not isinstance(title, str) or not title.strip(): raise ValueError()
                    title_shortened = len(title) > 255
                    if title_shortened:
                        title = title[:254].rstrip() + '…'
                    if not all(re.fullmatch(r'\d{2}:\d{2}', block[k]) for k in ('start', 'end')): raise ValueError()
                    start = datetime.fromisoformat(day + 'T' + block['start']).replace(tzinfo=MANILA)
                    end = datetime.fromisoformat(day + 'T' + block['end']).replace(tzinfo=MANILA)
                    if end <= start: raise ValueError()
                except (KeyError, TypeError, ValueError): raise ValueError('A task block has an invalid ID, title, or time.') from None
                ids.add(identity)
                key = hashlib.sha256((day + '\0' + identity).encode()).hexdigest()
                owned = self.state.setdefault('owned', {}).get(key)
                operation = {'kind': 'create', 'key': key, 'calendarId': calendar, 'title': title,
                             'start': start.isoformat(), 'end': end.isoformat()}
                if owned and owned.get('eventId'):
                    if owned['calendarId'] != calendar: raise ValueError('Stored task belongs to another calendar.')
                    remote = self._request('GET', self._event_path(calendar, owned['eventId']))
                    if remote.get('attendees') or not remote.get('@odata.etag'):
                        raise ValueError('Cannot safely update an event with attendees or missing version.')
                    operation.update(kind='update', eventId=owned['eventId'], etag=remote['@odata.etag'])
                else:
                    snapshot = hashlib.sha256(json.dumps(operation, sort_keys=True).encode()).hexdigest()
                    if owned and owned.get('snapshot') != snapshot:
                        raise ValueError('An earlier task creation is unconfirmed. Retry its original contents before changing this task.')
                    operation['snapshot'] = snapshot
                    operation['transactionId'] = owned.get('transactionId') if owned else str(uuid.uuid4())
                # Presentation metadata must not enter the recoverable event snapshot.
                if title_shortened:
                    operation['titleShortened'] = True
                operations.append(operation)
            operations, _ = self._check_availability(operations, self.cached_busy(day)['busy'])
            preview_id = uuid.uuid4().hex
            preview = {'previewId': preview_id, 'expiresAt': time.time() + FRESH_SECONDS,
                       'planId': plan['id'], 'date': day, 'operations': operations,
                       'accountId': self.state['accountId'], 'calendarId': calendar, 'completed': []}
            self.previews[preview_id] = copy.deepcopy(preview)
            return {k: copy.deepcopy(v) for k, v in preview.items() if k not in ('accountId', 'completed')}

    def publish(self, preview_id: str) -> dict:
        with self.lock:
            preview = self.previews.get(preview_id)
            if not preview or preview['expiresAt'] < time.time(): raise ValueError('This Outlook preview expired. Preview the plan again.')
            self._token()
            if preview['accountId'] != self.state.get('accountId') or preview['calendarId'] != self.state.get('calendarId'):
                raise ValueError('The Microsoft account or calendar changed. Preview again.')
            completed, failed = preview['completed'], []
            dependencies = {}
            remaining = [operation for operation in preview['operations'] if operation['key'] not in completed]
            if remaining:
                availability = self.sync(preview['date'])
                if availability['stale']:
                    raise ValueError('Outlook availability could not be refreshed. No task events were written.')
                if preview['accountId'] != self.state.get('accountId') or preview['calendarId'] != self.state.get('calendarId'):
                    raise ValueError('The Microsoft account or calendar changed. Preview again.')
                for operation in remaining:
                    owned = self.state.get('owned', {}).get(operation['key'], {})
                    if (operation['kind'] == 'create' and owned.get('recovered')
                            and operation['key'] in self.verified_recoveries
                            and owned.get('eventId') and owned.get('calendarId') == operation['calendarId']
                            and owned.get('transactionId') == operation['transactionId']
                            and owned.get('snapshot') == operation['snapshot']):
                        completed.append(operation['key'])
                remaining = [operation for operation in remaining if operation['key'] not in completed]
                remaining, dependencies = self._check_availability(remaining, availability['busy'])
            for operation in remaining:
                if operation['key'] in completed: continue
                try:
                    if not dependencies.get(operation['key'], set()) <= set(completed):
                        raise ValueError('A preceding task move failed. Retry this approval after that move succeeds.')
                    calendar, key = operation['calendarId'], operation['key']
                    owned = self.state.setdefault('owned', {}).get(key)
                    body = {'subject': operation['title'],
                            'start': {'dateTime': operation['start'][:19], 'timeZone': 'Singapore Standard Time'},
                            'end': {'dateTime': operation['end'][:19], 'timeZone': 'Singapore Standard Time'}}
                    if operation['kind'] == 'update':
                        if not owned or owned.get('eventId') != operation['eventId'] or owned['calendarId'] != calendar:
                            raise ValueError('The owned event mapping changed. Preview again.')
                        path = self._event_path(calendar, operation['eventId'])
                        remote = self._request('GET', path)
                        if remote.get('@odata.etag') != operation['etag'] or remote.get('attendees'):
                            raise ValueError('Outlook event changed since preview. Sync and preview again.')
                        result = self._request('PATCH', path, body=body, etag=operation['etag'])
                    else:
                        if owned and owned.get('eventId'): raise ValueError('Another approval already created this task. Preview again.')
                        if owned and owned.get('transactionId') != operation['transactionId']:
                            raise ValueError('Another preview reserved this task. Preview again.')
                        self.state['owned'][key] = {'calendarId': calendar, 'transactionId': operation['transactionId'], 'snapshot': operation['snapshot']}
                        self._save()
                        body.update(transactionId=operation['transactionId'], showAs='busy', isReminderOn=False)
                        result = self._request('POST', self._event_path(calendar), body=body)
                    if not result.get('id'): raise ValueError('Microsoft did not confirm the task event.')
                    self.state['owned'][key] = {'calendarId': calendar, 'eventId': result['id'],
                                               'etag': result.get('@odata.etag'), 'transactionId': operation.get('transactionId')}
                    completed.append(key)
                    self._save()
                except Exception as error:
                    failed.append({'key': operation['key'], 'error': str(error) if isinstance(error, ValueError) else 'Outlook task write failed. Retry this approval.'})
            return {'previewId': preview_id, 'completed': list(completed), 'failed': failed,
                    'partial': bool(completed and failed), 'success': not failed}
