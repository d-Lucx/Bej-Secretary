import unittest
from datetime import datetime

from planner import MANILA, make_plan
from planning_metadata import source_due


class PlanningMetadataTests(unittest.TestCase):
    def test_only_explicit_valid_task_due_markers_are_dates(self):
        self.assertEqual(source_due('Review 📅 2026-11-16')['dueDate'], '2026-11-16')
        self.assertEqual(source_due('Review due:: 2026-11-17')['dueDate'], '2026-11-17')
        self.assertIsNone(source_due('Review tomorrow or 2026-11-16')['dueDate'])
        for title in ['Review 📅 2026-02-30', 'Review due:: tomorrow',
                      'Review 📅 2026-11-16 due:: 2026-11-17', 'Review due::',
                      'Review 📅 2026-11-16 due::']:
            with self.subTest(title=title):
                result = source_due(title)
                self.assertIsNone(result['dueDate'])
                self.assertTrue(result['dueWarning'])

    def test_capacity_goes_to_due_tasks_then_explicit_priority_without_moving_deadlines(self):
        tasks = [self.task('later', 'urgent', '2026-11-20'), self.task('normal'),
                 self.task('today', 'low', '2026-11-16'), self.task('late', 'normal', '2026-11-15'),
                 self.task('important', 'high')]
        plan = make_plan(tasks, '2026-11-16', 60, self.now())
        self.assertEqual([b['id'] for b in plan['blocks']], ['late', 'today'])
        self.assertEqual([b['id'] for b in plan['unscheduled']], ['later', 'important', 'normal'])
        self.assertEqual(tasks[3]['dueDate'], '2026-11-15')
        self.assertTrue(any(w['taskId'] == 'late' for w in plan['deadlineWarnings']))

    def test_due_today_overflow_has_a_visible_risk_and_ties_preserve_input_order(self):
        first, second = self.task('first', due='2026-11-16'), self.task('second', due='2026-11-16')
        plan = make_plan([first, second], '2026-11-16', 30, self.now())
        self.assertEqual(plan['blocks'][0]['id'], 'first')
        self.assertTrue(any(w['taskId'] == 'second' and 'fit' in w['message'] for w in plan['deadlineWarnings']))

    def test_invalid_metadata_fails_before_planning(self):
        for change in [{'dueDate': '2026-02-30'}, {'priority': 'do everything'}, {'dueDate': True}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                make_plan([{**self.task('a'), **change}], '2026-11-16', 30, self.now())

    @staticmethod
    def task(identity, priority='normal', due=None):
        return {'id': identity, 'title': identity, 'category': 'work', 'minutes': 30,
                'priority': priority, 'dueDate': due}

    @staticmethod
    def now():
        return datetime(2026, 11, 16, 7, tzinfo=MANILA)
