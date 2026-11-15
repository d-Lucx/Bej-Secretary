import hashlib
import unittest
from calendar_task_ids import resolve_calendar_ids
from planner import task_identity


class CalendarTaskIdentityTests(unittest.TestCase):
    def test_published_legacy_id_wins_over_an_older_unpublished_draft(self):
        task = {'id': 'old-unpublished', 'title': 'Review', 'source': 'Work.md', 'heading': 'Tasks'}
        alias = {task_identity(task): {'old-unpublished', 'new-published'}}
        key = hashlib.sha256('2026-11-16\0new-published'.encode()).hexdigest()
        result = resolve_calendar_ids([task], '2026-11-16', alias, {key: {'calendarId': 'bej', 'eventId': 'event'}}, 'bej')
        self.assertEqual(result[0]['id'], 'new-published')
        self.assertEqual(task['id'], 'old-unpublished')

    def test_multiple_published_aliases_fail_closed_without_deleting_events(self):
        task = {'id': 'old', 'title': 'Review', 'source': 'Work.md'}
        alias = {task_identity(task): {'old', 'new'}}
        owned = {hashlib.sha256(f'2026-11-16\0{key}'.encode()).hexdigest(): {'calendarId': 'bej', 'eventId': key} for key in ('old', 'new')}
        with self.assertRaisesRegex(ValueError, 'multiple'):
            resolve_calendar_ids([task], '2026-11-16', alias, owned, 'bej')
        self.assertEqual(len(owned), 2)

    def test_reserved_uncertain_creation_is_reused_instead_of_bypassed(self):
        task = {'id': 'new', 'title': 'Review', 'source': 'Work.md'}
        alias = {task_identity(task): {'old'}}
        key = hashlib.sha256('2026-11-16\0old'.encode()).hexdigest()
        result = resolve_calendar_ids([task], '2026-11-16', alias, {key: {'calendarId': 'bej', 'transactionId': 'reserved'}}, 'bej')
        self.assertEqual(result[0]['id'], 'old')
