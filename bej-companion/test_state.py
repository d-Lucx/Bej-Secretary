import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from planner import MANILA
from state import LocalStore


def draft(day='2026-11-16', start='08:00'):
    return {'id': 'plan1', 'date': day, 'blocks': [{'id': 'task1', 'title': 'Review work', 'start': start, 'end': '08:30', 'category': 'work', 'minutes': 30}], 'unscheduled': []}


class StateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
        self.store = LocalStore(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_plans_and_saved_paths_survive_restart(self):
        self.store.put_plan(draft())
        self.store.set_saved_path('plan1', 'vault/Bej Plans/plan.md')
        again = LocalStore(self.path)
        self.assertEqual(again.get_plan('plan1')['blocks'][0]['title'], 'Review work')
        self.assertEqual(again.saved_path('plan1'), 'vault/Bej Plans/plan.md')

    def test_arming_same_block_twice_does_not_duplicate(self):
        now = datetime(2026, 11, 16, 7, 0, tzinfo=MANILA)
        self.store.arm(draft(), 'discord', now)
        self.store.arm(draft(), 'discord', now)
        self.assertEqual(len(self.store.reminders()), 1)
        self.assertEqual(self.store.reminders()[0]['state'], 'pending')

    def test_rearm_updates_pending_details_without_duplicate_delivery(self):
        now = datetime(2026, 11, 16, 7, 0, tzinfo=MANILA)
        self.store.arm(draft(), 'discord', now)
        revised = draft()
        revised['blocks'][0]['end'] = '09:00'
        self.store.arm(revised, 'discord', now)
        self.assertEqual(len(self.store.reminders()), 1)
        self.assertEqual(self.store.reminders()[0]['data']['end'], '09:00')

    def test_changed_time_cancels_old_pending_reminder(self):
        now = datetime(2026, 11, 16, 7, 0, tzinfo=MANILA)
        self.store.arm(draft(), 'discord', now)
        self.store.arm(draft(start='09:00'), 'discord', now)
        states = sorted(r['state'] for r in self.store.reminders())
        self.assertEqual(states, ['canceled', 'pending'])

    def test_returning_to_original_time_reactivates_only_the_canceled_record(self):
        now = datetime(2026, 11, 16, 7, 0, tzinfo=MANILA)
        self.store.arm(draft(), 'discord', now)
        self.store.arm(draft(start='09:00'), 'discord', now)
        self.store.arm(draft(), 'discord', now)
        active = [item for item in self.store.reminders() if item['state'] == 'pending']
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]['data']['start'], '08:00')

    def test_claim_is_atomic_and_interrupted_delivery_becomes_uncertain(self):
        now = datetime(2026, 11, 16, 8, 0, tzinfo=MANILA)
        self.store.arm(draft(), 'discord', now - timedelta(hours=1))
        item = self.store.claim(now)
        self.assertIsNotNone(item)
        self.assertIsNone(self.store.claim(now))
        self.store.recover_interrupted()
        self.assertEqual(self.store.reminders()[0]['state'], 'uncertain')
        self.assertIsNone(self.store.claim(now))

    def test_late_and_sleep_time_reminders_are_not_delivered(self):
        now = datetime(2026, 11, 16, 7, 0, tzinfo=MANILA)
        self.store.arm(draft(), 'discord', now)
        self.assertIsNone(self.store.claim(now.replace(hour=10)))
        self.assertEqual(self.store.reminders()[0]['state'], 'missed')
        self.store.arm(draft(start='21:59'), 'discord', now)
        self.assertIsNone(self.store.claim(now.replace(hour=22)))
        self.assertEqual(self.store.reminders()[0]['state'], 'pending')


if __name__ == '__main__':
    unittest.main()
