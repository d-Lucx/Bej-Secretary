import unittest
from datetime import datetime
from planner import MANILA, make_plan
from reflow import reflow_plan


class ReflowTests(unittest.TestCase):
    def test_emergency_moves_flexible_work_without_changing_the_original(self):
        now = datetime(2026, 11, 16, 7, 0, tzinfo=MANILA)
        original = make_plan([{'id': 't', 'title': 'A task', 'category': 'work', 'minutes': 30}], '2026-11-16', 240, now)
        changed = reflow_plan(original, '08:00', '10:00', 'Unexpected appointment', now=now)
        self.assertEqual(original['blocks'][0]['start'], '08:00')
        self.assertEqual(changed['blocks'][0]['start'], '10:00')
        self.assertEqual(changed['change']['movedCount'], 1)
        self.assertNotEqual(changed['id'], original['id'])

    def test_full_work_window_block_leaves_task_unscheduled(self):
        now = datetime(2026, 11, 16, 7, 0, tzinfo=MANILA)
        original = make_plan([{'id': 't', 'title': 'A task', 'category': 'work', 'minutes': 30}], '2026-11-16', 240, now)
        changed = reflow_plan(original, '08:00', '17:00', 'Emergency', now=now)
        self.assertEqual(changed['blocks'], [])
        self.assertEqual(len(changed['unscheduled']), 1)


if __name__ == '__main__': unittest.main()
