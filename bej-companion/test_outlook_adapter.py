import json
import tempfile
import time
import unittest
from pathlib import Path

from outlook_adapter import OutlookAdapter

CLIENT = '12345678-1234-1234-1234-123456789abc'


class Store:
    def __init__(self): self.values = {}
    def get(self, name): return self.values.get(name)
    def set(self, name, value): self.values[name] = value


class App:
    def __init__(self, *args, **kwargs): self.token_cache = kwargs['token_cache']
    def get_accounts(self): return [{'home_account_id': 'account-one'}]
    def acquire_token_silent(self, scopes, account): return {'access_token': 'SECRET'}
    def initiate_device_flow(self, scopes):
        return {'user_code': 'CODE', 'verification_uri': 'https://microsoft.com/devicelogin', 'expires_in': 900, 'device_code': 'PRIVATE'}
    def acquire_token_by_device_flow(self, flow): return {'access_token': 'SECRET'}


class Response:
    def __init__(self, data, status=200): self.data, self.status_code = data, status
    def json(self): return self.data


class Http:
    def __init__(self): self.responses, self.calls = [], []
    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if not self.responses: raise OSError('network SECRET')
        response = self.responses.pop(0)
        if isinstance(response, Exception): raise response
        return response


class OutlookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.http, self.store = Http(), Store()
        self.adapter = OutlookAdapter(Path(self.tmp.name), self.store, http=self.http, app_factory=App)
        self.adapter.configure(CLIENT)

    def sync_empty(self):
        self.http.responses += [Response({'value': [{'id': 'main', 'name': 'Calendar'}, {'id': 'bej', 'name': 'Bej'}]}), Response({'value': []}), Response({'value': []})]
        return self.adapter.sync('2026-11-16')

    def publish(self, preview_id, *, busy=None, busy_bej=None):
        preview = self.adapter.previews.get(preview_id)
        if preview and preview['expiresAt'] > time.time() and any(op['key'] not in preview['completed'] for op in preview['operations']):
            self.http.responses[0:0] = [Response({'value': [{'id': 'main', 'name': 'Calendar'}, {'id': 'bej', 'name': 'Bej'}]}), Response({'value': busy or []}), Response({'value': busy_bej or []})]
        return self.adapter.publish(preview_id)

    def event(self, identity='meeting', start='2026-11-16T00:00:00', end='2026-11-16T00:30:00'):
        return {'id': identity, 'showAs': 'busy', 'start': {'dateTime': start, 'timeZone': 'UTC'}, 'end': {'dateTime': end, 'timeZone': 'UTC'}}

    def plan(self, title='Task'):
        return {'id': 'plan', 'date': '2026-11-16', 'blocks': [{'id': 'task', 'title': title, 'start': '08:00', 'end': '08:30'}]}

    def test_not_configured_and_invalid_client_never_call_network(self):
        other = OutlookAdapter(Path(self.tmp.name) / 'other', self.store, http=self.http, app_factory=App)
        self.assertFalse(other.status()['configured'])
        with self.assertRaises(ValueError): other.begin_login()
        with self.assertRaises(ValueError): other.configure('bad')
        self.assertEqual([], self.http.calls)

    def test_login_returns_only_safe_device_fields(self):
        result = self.adapter.begin_login()
        deadline = time.monotonic() + 2
        while self.adapter.status()['authPending'] and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertFalse(self.adapter.status()['authPending'])
        self.assertEqual({'user_code', 'verification_uri', 'expires_in'}, set(result))
        self.assertNotIn('SECRET', json.dumps(self.adapter.status()))

    def test_sync_reads_each_calendar_and_recurrence_pages(self):
        event = {'id': 'meeting', 'showAs': 'busy', 'start': {'dateTime': '2026-11-16T01:00:00', 'timeZone': 'UTC'}, 'end': {'dateTime': '2026-11-16T02:00:00', 'timeZone': 'UTC'}}
        self.http.responses += [Response({'value': [{'id': 'main', 'name': 'Calendar'}, {'id': 'bej', 'name': 'Bej'}]}), Response({'value': [event], '@odata.nextLink': 'https://graph.microsoft.com/v1.0/me/calendars/main/calendarView?$skip=1'}), Response({'value': []}), Response({'value': []})]
        result = self.adapter.sync('2026-11-16')
        self.assertFalse(result['stale'])
        self.assertEqual('2026-11-16T09:00:00+08:00', result['busy'][0]['start'])
        self.assertEqual(4, len(self.http.calls))
        for _, _, kwargs in self.http.calls: self.assertFalse(kwargs['allow_redirects'])

    def test_bad_pagination_does_not_leak_token_and_preserves_cache(self):
        self.sync_empty()
        self.http.responses += [Response({'value': [], '@odata.nextLink': 'https://evil.invalid/steal'})]
        result = self.adapter.sync('2026-11-16')
        self.assertTrue(result['stale'])
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertTrue(all('evil' not in call[1] for call in self.http.calls))

    def test_duplicate_calendar_refuses_writes(self):
        self.http.responses += [Response({'value': [{'id': 'a', 'name': 'Bej'}, {'id': 'b', 'name': 'Bej'}]})]
        self.assertIn('error', self.adapter.sync('2026-11-16'))
        self.assertTrue(all(call[0] == 'GET' for call in self.http.calls))

    def test_create_calendar_only_on_sync(self):
        self.assertEqual([], self.http.calls)
        self.http.responses += [Response({'value': [{'id': 'main', 'name': 'Calendar'}]}), Response({'id': 'bej', 'name': 'Bej'}, 201), Response({'value': []}), Response({'value': []})]
        self.assertFalse(self.adapter.sync('2026-11-16')['stale'])
        self.assertEqual({'name': 'Bej'}, self.http.calls[1][2]['json'])

    def test_preview_binds_snapshot_and_publish_is_idempotent(self):
        self.sync_empty()
        plan = self.plan()
        preview = self.adapter.preview(plan)
        plan['blocks'][0]['title'] = 'Altered'
        self.assertEqual('Task', preview['operations'][0]['title'])
        self.http.responses += [Response({'id': 'event', '@odata.etag': 'v1'}, 201)]
        result = self.publish(preview['previewId'])
        self.assertEqual(1, len(result['completed']))
        body = self.http.calls[-1][2]['json']
        self.assertEqual('Task', body['subject'])
        self.assertEqual('2026-11-16T08:00:00', body['start']['dateTime'])
        self.assertNotIn('attendees', body)
        count = len(self.http.calls)
        self.publish(preview['previewId'])
        self.assertEqual(count, len(self.http.calls))

    def test_retry_uses_same_transaction_id_after_uncertain_failure(self):
        self.sync_empty()
        preview = self.adapter.preview(self.plan())
        failed = self.publish(preview['previewId'])
        self.assertEqual(1, len(failed['failed']))
        transaction = self.http.calls[-1][2]['json']['transactionId']
        self.http.responses += [Response({'id': 'event', '@odata.etag': 'v1'}, 201)]
        self.publish(preview['previewId'])
        self.assertEqual(transaction, self.http.calls[-1][2]['json']['transactionId'])

    def test_committed_create_with_lost_response_is_recovered_without_duplicate_post(self):
        self.sync_empty()
        preview = self.adapter.preview(self.plan())
        self.assertFalse(self.publish(preview['previewId'])['success'])
        operation = preview['operations'][0]
        remote = self.event('committed')
        remote.update(transactionId=operation['transactionId'], subject='Task', attendees=[], body={'contentType': 'text', 'content': ''}, **{'@odata.etag': 'v1'})
        posts = sum(method == 'POST' for method, _, _ in self.http.calls)
        result = self.publish(preview['previewId'], busy_bej=[remote])
        self.assertTrue(result['success'])
        self.assertEqual([operation['key']], result['completed'])
        self.assertEqual(posts, sum(method == 'POST' for method, _, _ in self.http.calls))
        self.assertEqual('committed', self.adapter.state['owned'][operation['key']]['eventId'])

    def test_reconciliation_rejects_mismatched_contents_and_attendees(self):
        for changes in ({'subject': 'Someone else'}, {'body': {'contentType': 'text', 'content': 'Unapproved notes'}}, {'attendees': [{'emailAddress': {'address': 'person@example.com'}}]}, {'end': {'dateTime': '2026-11-16T01:00:00', 'timeZone': 'UTC'}}):
            with self.subTest(changes=changes):
                self.sync_empty()
                preview = self.adapter.preview(self.plan())
                self.publish(preview['previewId'])
                operation = preview['operations'][0]
                remote = self.event('committed')
                remote.update(transactionId=operation['transactionId'], subject='Task', attendees=[], **{'@odata.etag': 'v1'})
                remote.update(changes)
                before = len(self.http.calls)
                with self.assertRaises(ValueError): self.publish(preview['previewId'], busy_bej=[remote])
                self.assertNotIn('eventId', self.adapter.state['owned'][operation['key']])
                self.assertTrue(all(method == 'GET' for method, _, _ in self.http.calls[before:]))

    def test_restart_reconciles_pending_create_and_allows_new_update_preview(self):
        self.sync_empty()
        preview = self.adapter.preview(self.plan())
        self.publish(preview['previewId'])
        transaction = preview['operations'][0]['transactionId']
        self.adapter = OutlookAdapter(Path(self.tmp.name), self.store, http=self.http, app_factory=App)
        remote = self.event('committed')
        remote.update(transactionId=transaction, subject='Task', attendees=[], **{'@odata.etag': 'v1'})
        self.http.responses += [Response({'value': [{'id': 'bej', 'name': 'Bej'}]}), Response({'value': [remote]})]
        self.assertFalse(self.adapter.sync('2026-11-16')['stale'])
        self.http.responses += [Response(remote)]
        recovered = self.adapter.preview(self.plan())
        self.assertEqual('update', recovered['operations'][0]['kind'])
        self.assertEqual('committed', recovered['operations'][0]['eventId'])

    def test_matching_transaction_on_another_calendar_is_not_appropriated(self):
        self.sync_empty()
        preview = self.adapter.preview(self.plan())
        self.publish(preview['previewId'])
        operation = preview['operations'][0]
        remote = self.event('unrelated')
        remote.update(transactionId=operation['transactionId'], subject='Task', attendees=[], **{'@odata.etag': 'v1'})
        with self.assertRaises(ValueError): self.publish(preview['previewId'], busy=[remote])
        self.assertNotIn('eventId', self.adapter.state['owned'][operation['key']])

    def test_duplicate_matching_transactions_are_not_appropriated(self):
        self.sync_empty()
        preview = self.adapter.preview(self.plan())
        self.publish(preview['previewId'])
        operation = preview['operations'][0]
        events = [self.event('first'), self.event('second')]
        for event in events:
            event.update(transactionId=operation['transactionId'], subject='Task', attendees=[], **{'@odata.etag': 'v1'})
        with self.assertRaises(ValueError): self.publish(preview['previewId'], busy_bej=events)
        self.assertNotIn('eventId', self.adapter.state['owned'][operation['key']])

    def test_recovered_creation_requires_current_sync_proof_before_completion(self):
        self.sync_empty()
        preview = self.adapter.preview(self.plan())
        self.publish(preview['previewId'])
        operation = preview['operations'][0]
        remote = self.event('committed')
        remote.update(transactionId=operation['transactionId'], subject='Task', attendees=[], **{'@odata.etag': 'v1'})
        self.http.responses += [Response({'value': [{'id': 'bej', 'name': 'Bej'}]}), Response({'value': [remote]})]
        self.adapter.sync('2026-11-16')
        # The event disappeared after reconciliation but before this approval retry.
        result = self.publish(preview['previewId'])
        self.assertFalse(result['success'])
        self.assertEqual([], result['completed'])

    def test_update_refuses_remote_changes_after_preview(self):
        self.sync_empty()
        first = self.adapter.preview(self.plan())
        self.http.responses += [Response({'id': 'event', '@odata.etag': 'v1'}, 201)]
        self.publish(first['previewId'])
        self.http.responses += [Response({'id': 'event', '@odata.etag': 'v1', 'attendees': []})]
        second = self.adapter.preview(self.plan('Updated'))
        self.http.responses += [Response({'id': 'event', '@odata.etag': 'v2', 'attendees': []})]
        result = self.publish(second['previewId'])
        self.assertEqual(1, len(result['failed']))
        self.assertEqual('GET', self.http.calls[-1][0])

    def test_update_uses_if_match_and_changes_only_approved_fields(self):
        self.sync_empty()
        first = self.adapter.preview(self.plan())
        self.http.responses += [Response({'id': 'event', '@odata.etag': 'v1'}, 201)]
        self.publish(first['previewId'])
        self.http.responses += [Response({'id': 'event', '@odata.etag': 'v1', 'attendees': []})]
        second = self.adapter.preview(self.plan('Updated'))
        self.http.responses += [Response({'id': 'event', '@odata.etag': 'v1', 'attendees': []}), Response({'id': 'event', '@odata.etag': 'v2'})]
        self.assertTrue(self.publish(second['previewId'])['success'])
        method, url, args = self.http.calls[-1]
        self.assertEqual('PATCH', method)
        self.assertEqual('v1', args['headers']['If-Match'])
        self.assertEqual({'subject', 'start', 'end'}, set(args['json']))

    def test_expired_approval_never_writes(self):
        self.sync_empty()
        preview = self.adapter.preview(self.plan())
        self.adapter.previews[preview['previewId']]['expiresAt'] = time.time() - 1
        count = len(self.http.calls)
        with self.assertRaises(ValueError): self.publish(preview['previewId'])
        self.assertEqual(count, len(self.http.calls))

    def test_uncertain_create_cannot_reuse_transaction_for_changed_content(self):
        self.sync_empty()
        preview = self.adapter.preview(self.plan())
        self.publish(preview['previewId'])
        with self.assertRaises(ValueError): self.adapter.preview(self.plan('Changed'))

    def test_offline_cache_survives_restart_without_tokens_on_disk(self):
        self.sync_empty()
        self.adapter.sync('2026-11-16')
        other = OutlookAdapter(Path(self.tmp.name), self.store, http=self.http, app_factory=App)
        self.assertTrue(other.cached_busy('2026-11-16')['stale'])
        self.assertIsNotNone(other.cached_busy('2026-11-16')['lastSyncedAt'])
        self.assertNotIn('SECRET', ''.join(p.read_text() for p in Path(self.tmp.name).iterdir()))

    def test_status_does_not_initialize_authentication_or_access_network(self):
        calls = []
        def forbidden(*args, **kwargs):
            calls.append(True)
            raise AssertionError('status started authentication')
        other = OutlookAdapter(Path(self.tmp.name) / 'other', self.store, http=self.http, app_factory=forbidden)
        status = other.configure(CLIENT)
        self.assertTrue(status['configured'])
        self.assertIsNone(other.error)
        self.assertIsNone(other.app)
        self.assertEqual([], calls)

    def test_preview_requires_fresh_sync_and_rejects_invalid_blocks(self):
        with self.assertRaises(ValueError): self.adapter.preview(self.plan())
        self.sync_empty()
        plan = self.plan()
        plan['blocks'][0]['end'] = '07:00'
        with self.assertRaises(ValueError): self.adapter.preview(plan)

    def test_preview_refuses_collision_on_another_calendar(self):
        self.http.responses += [Response({'value': [{'id': 'main', 'name': 'Calendar'}, {'id': 'bej', 'name': 'Bej'}]}), Response({'value': [self.event()]}), Response({'value': []})]
        self.adapter.sync('2026-11-16')
        with self.assertRaises(ValueError): self.adapter.preview(self.plan())

    def test_publish_refuses_appointment_added_after_preview(self):
        self.sync_empty()
        preview = self.adapter.preview(self.plan())
        before = len(self.http.calls)
        with self.assertRaises(ValueError): self.publish(preview['previewId'], busy=[self.event()])
        self.assertTrue(all(method == 'GET' for method, _, _ in self.http.calls[before:]))

    def test_update_excludes_only_its_own_calendar_event(self):
        self.sync_empty()
        initial = self.adapter.preview(self.plan())
        self.http.responses += [Response({'id': 'owned', '@odata.etag': 'v1'}, 201)]
        self.publish(initial['previewId'])
        self.http.responses += [Response({'value': [{'id': 'main', 'name': 'Calendar'}, {'id': 'bej', 'name': 'Bej'}]}), Response({'value': []}), Response({'value': [self.event('owned')]})]
        self.adapter.sync('2026-11-16')
        self.http.responses += [Response({'id': 'owned', '@odata.etag': 'v1', 'attendees': []})]
        preview = self.adapter.preview(self.plan('Updated'))
        self.assertEqual('update', preview['operations'][0]['kind'])
        self.http.responses += [Response({'id': 'owned', '@odata.etag': 'v1', 'attendees': []}), Response({'id': 'owned', '@odata.etag': 'v2'})]
        self.assertTrue(self.publish(preview['previewId'], busy_bej=[self.event('owned')])['success'])
        self.adapter.state['days']['2026-11-16']['busy'].append({'calendarId': 'main', 'eventId': 'owned', 'start': '2026-11-16T08:00:00+08:00', 'end': '2026-11-16T08:30:00+08:00'})
        self.http.responses += [Response({'id': 'owned', '@odata.etag': 'v2', 'attendees': []})]
        with self.assertRaises(ValueError): self.adapter.preview(self.plan('Updated'))

    def test_publish_offline_refuses_writes_even_with_fresh_cache(self):
        self.sync_empty()
        preview = self.adapter.preview(self.plan())
        before = len(self.http.calls)
        with self.assertRaises(ValueError): self.adapter.publish(preview['previewId'])
        self.assertTrue(all(method == 'GET' for method, _, _ in self.http.calls[before:]))

    def test_adjacent_busy_event_does_not_block_preview(self):
        self.http.responses += [Response({'value': [{'id': 'main', 'name': 'Calendar'}, {'id': 'bej', 'name': 'Bej'}]}), Response({'value': [self.event(start='2026-11-15T23:30:00', end='2026-11-16T00:00:00')]}), Response({'value': []})]
        self.adapter.sync('2026-11-16')
        self.assertEqual(1, len(self.adapter.preview(self.plan())['operations']))

    def test_plan_metadata_never_becomes_event_content(self):
        self.sync_empty()
        plan = self.plan()
        plan['blocks'][0].update(source='PRIVATE_SOURCE', body='PRIVATE_BODY', attendees=['other@example.com'])
        preview = self.adapter.preview(plan)
        self.http.responses += [Response({'id': 'owned', '@odata.etag': 'v1'}, 201)]
        self.publish(preview['previewId'])
        serialized = json.dumps(preview) + json.dumps(self.http.calls[-1][2]['json'])
        for private in ('PRIVATE_SOURCE', 'PRIVATE_BODY', 'other@example.com'): self.assertNotIn(private, serialized)

    def test_partial_publish_retries_only_failed_operation(self):
        self.sync_empty()
        plan = self.plan()
        plan['blocks'].append({'id': 'second', 'title': 'Second', 'start': '09:00', 'end': '09:30'})
        preview = self.adapter.preview(plan)
        self.http.responses += [Response({'id': 'event', '@odata.etag': 'v1'}, 201)]
        result = self.publish(preview['previewId'])
        self.assertTrue(result['partial'])
        self.assertEqual(1, len(result['completed']))
        self.http.responses += [Response({'id': 'second-event', '@odata.etag': 'v1'}, 201)]
        result = self.publish(preview['previewId'])
        self.assertTrue(result['success'])
        self.assertEqual(2, len(result['completed']))
        self.assertEqual('Second', self.http.calls[-1][2]['json']['subject'])

    def test_preview_cannot_modify_approved_operations_by_reference(self):
        self.sync_empty()
        preview = self.adapter.preview(self.plan())
        preview['operations'][0]['calendarId'] = 'unrelated'
        preview['operations'][0]['title'] = 'Altered'
        self.http.responses += [Response({'id': 'event', '@odata.etag': 'v1'}, 201)]
        self.assertTrue(self.publish(preview['previewId'])['success'])
        self.assertIn('/calendars/bej/events', self.http.calls[-1][1])
        self.assertEqual('Task', self.http.calls[-1][2]['json']['subject'])

    def test_update_with_attendees_is_rejected_before_any_write(self):
        self.sync_empty()
        first = self.adapter.preview(self.plan())
        self.http.responses += [Response({'id': 'event', '@odata.etag': 'v1'}, 201)]
        self.publish(first['previewId'])
        self.http.responses += [Response({'id': 'event', '@odata.etag': 'v1', 'attendees': [{'emailAddress': {'address': 'person@example.com'}}]})]
        with self.assertRaises(ValueError): self.adapter.preview(self.plan('Updated'))
        self.assertEqual('GET', self.http.calls[-1][0])

    def test_reconfigure_discards_account_bound_calendar_and_approvals(self):
        self.sync_empty()
        preview = self.adapter.preview(self.plan())
        self.adapter.configure('22345678-1234-1234-1234-123456789abc')
        self.assertIsNone(self.adapter.status()['calendarId'])
        with self.assertRaises(ValueError): self.publish(preview['previewId'])

    def batch_fixture(self, *, cycle=False):
        self.sync_empty()
        initial = self.plan('A')
        initial['blocks'].append({'id': 'second', 'title': 'B', 'start': '08:30', 'end': '09:00'})
        first = self.adapter.preview(initial)
        self.http.responses += [Response({'id': 'a', '@odata.etag': 'a1'}, 201), Response({'id': 'b', '@odata.etag': 'b1'}, 201)]
        self.assertTrue(self.publish(first['previewId'])['success'])
        old = [self.event('a'), self.event('b', start='2026-11-16T00:30:00', end='2026-11-16T01:00:00')]
        self.http.responses += [Response({'value': [{'id': 'bej', 'name': 'Bej'}]}), Response({'value': old})]
        self.adapter.sync(initial['date'])
        initial['blocks'][0].update(start='08:30', end='09:00')
        initial['blocks'][1].update(start='08:00' if cycle else '09:00', end='08:30' if cycle else '09:30')
        self.http.responses += [Response({'id': 'a', '@odata.etag': 'a1', 'attendees': []}), Response({'id': 'b', '@odata.etag': 'b1', 'attendees': []})]
        return initial, old

    def test_batch_shift_moves_later_block_first(self):
        plan, old = self.batch_fixture()
        preview = self.adapter.preview(plan)
        self.assertEqual(['B', 'A'], [op['title'] for op in preview['operations']])
        before = len(self.http.calls)
        self.http.responses += [Response({'id': 'b', '@odata.etag': 'b1', 'attendees': []}), Response({'id': 'b', '@odata.etag': 'b2'}), Response({'id': 'a', '@odata.etag': 'a1', 'attendees': []}), Response({'id': 'a', '@odata.etag': 'a2'})]
        self.assertTrue(self.publish(preview['previewId'], busy_bej=old)['success'])
        patches = [url.rsplit('/', 1)[-1] for method, url, _ in self.http.calls[before:] if method == 'PATCH']
        self.assertEqual(['b', 'a'], patches)

    def test_failed_predecessor_never_moves_dependent_into_occupied_slot(self):
        plan, old = self.batch_fixture()
        preview = self.adapter.preview(plan)
        before = len(self.http.calls)
        self.http.responses += [Response({'id': 'b', '@odata.etag': 'b1', 'attendees': []}), Response({}, 412)]
        result = self.publish(preview['previewId'], busy_bej=old)
        self.assertFalse(result['success'])
        self.assertEqual(2, len(result['failed']))
        patches = [url.rsplit('/', 1)[-1] for method, url, _ in self.http.calls[before:] if method == 'PATCH']
        self.assertEqual(['b'], patches)

    def test_batch_partial_retry_does_not_repeat_successful_predecessor(self):
        plan, old = self.batch_fixture()
        preview = self.adapter.preview(plan)
        self.http.responses += [Response({'id': 'b', '@odata.etag': 'b1', 'attendees': []}), Response({'id': 'b', '@odata.etag': 'b2'}), Response({'id': 'a', '@odata.etag': 'a1', 'attendees': []}), Response({}, 412)]
        first = self.publish(preview['previewId'], busy_bej=old)
        self.assertTrue(first['partial'])
        now = [old[0], self.event('b', start='2026-11-16T01:00:00', end='2026-11-16T01:30:00')]
        before = len(self.http.calls)
        self.http.responses += [Response({'id': 'a', '@odata.etag': 'a1', 'attendees': []}), Response({'id': 'a', '@odata.etag': 'a2'})]
        self.assertTrue(self.publish(preview['previewId'], busy_bej=now)['success'])
        patches = [url.rsplit('/', 1)[-1] for method, url, _ in self.http.calls[before:] if method == 'PATCH']
        self.assertEqual(['a'], patches)

    def test_batch_publish_rechecks_dependencies_against_fresh_slots(self):
        plan, old = self.batch_fixture()
        preview = self.adapter.preview(plan)
        # A's old slot moved into B's target after preview, creating a cycle.
        changed = [self.event('a', start='2026-11-16T01:00:00', end='2026-11-16T01:30:00'), old[1]]
        before = len(self.http.calls)
        with self.assertRaisesRegex(ValueError, 'separate approvals'):
            self.publish(preview['previewId'], busy_bej=changed)
        self.assertTrue(all(method == 'GET' for method, _, _ in self.http.calls[before:]))

    def test_batch_swap_cycle_requires_split_approvals(self):
        plan, _ = self.batch_fixture(cycle=True)
        with self.assertRaisesRegex(ValueError, 'separate approvals'):
            self.adapter.preview(plan)

    def test_batch_targets_must_not_overlap_each_other(self):
        self.sync_empty()
        plan = self.plan()
        plan['blocks'].append({'id': 'other', 'title': 'Other', 'start': '08:15', 'end': '08:45'})
        with self.assertRaises(ValueError): self.adapter.preview(plan)

    def test_batch_shift_does_not_ignore_external_busy_events(self):
        plan, old = self.batch_fixture()
        preview = self.adapter.preview(plan)
        with self.assertRaises(ValueError):
            self.publish(preview['previewId'], busy=[self.event('external', start='2026-11-16T01:00:00', end='2026-11-16T01:30:00')], busy_bej=old)


if __name__ == '__main__': unittest.main()
