"""Resolve proven source aliases to an existing owned calendar block, offline."""
import hashlib
from planner import task_identity


def resolve_calendar_ids(tasks, day, aliases, owned, calendar_id):
    resolved = []
    for task in tasks:
        candidates = set(aliases.get(task_identity(task), ())) | {task['id']}
        matches = {}
        if calendar_id:
            for identity in sorted(candidates):
                key = hashlib.sha256(f'{day}\0{identity}'.encode()).hexdigest()
                entry = owned.get(key)
                if entry and entry.get('calendarId') == calendar_id:
                    if entry.get('eventId'):
                        matches[identity] = ('event', entry['eventId'])
                    elif entry.get('transactionId'):
                        matches[identity] = ('transaction', entry['transactionId'])
                    else:
                        raise ValueError('An existing calendar mapping is incomplete. Review it before building another task block.')
        if len(set(matches.values())) > 1:
            raise ValueError('This source task has multiple existing Outlook blocks or unconfirmed creations. Review its calendar before scheduling it again; no events were changed.')
        identity = task['id'] if task['id'] in matches or not matches else next(iter(matches))
        resolved.append({**task, 'id': identity})
    return resolved
