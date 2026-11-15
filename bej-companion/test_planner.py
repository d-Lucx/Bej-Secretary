import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from planner import scan_vault, make_plan, save_plan

TZ = timezone(timedelta(hours=8))
NOW = datetime(2026, 11, 16, 7, 0, tzinfo=TZ)


def task(key='a', kind='work', minutes=30):
    return {'id': key, 'title': f'Task {key}', 'category': kind, 'minutes': minutes,
            'source': 'Projects.md', 'line': 2}


class VaultTests(unittest.TestCase):
    def test_scan_is_read_only_and_skips_fenced_completed_and_generated_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = '# Roadmap\n- [ ] Ship planner\n- [x] Done\n```md\n- [ ] Example\n```\n'
            note = root / 'Project.md'
            note.write_text(content, encoding='utf-8')
            (root / 'Bej Plans').mkdir()
            (root / 'Bej Plans' / 'old.md').write_text('- [ ] Duplicate', encoding='utf-8')
            before = note.read_bytes()
            result = scan_vault(root)
            self.assertEqual([t['title'] for t in result['tasks']], ['Ship planner'])
            self.assertEqual(result['tasks'][0]['line'], 2)
            self.assertEqual(result['tasks'][0]['source'], 'Project.md')
            self.assertTrue(result['tasks'][0]['needsReview'])
            self.assertEqual(note.read_bytes(), before)
            self.assertEqual(scan_vault(root)['tasks'][0]['id'], result['tasks'][0]['id'])

    def test_external_linked_note_is_not_read(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            external = Path(outside) / 'Secret.md'
            external.write_text('- [ ] Outside', encoding='utf-8')
            try:
                (root / 'Linked.md').symlink_to(external)
            except OSError:
                self.skipTest('Creating symlinks requires Windows developer mode')
            self.assertEqual(scan_vault(root)['tasks'], [])

    def test_tilde_fences_and_unclosed_fences_do_not_import_examples(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'Examples.md').write_text('~~~\n- [ ] Example\n~~~\n- [ ] Real\n```\n- [ ] Hidden', encoding='utf-8')
            self.assertEqual([t['title'] for t in scan_vault(root)['tasks']], ['Real'])


class ScheduleTests(unittest.TestCase):
    def test_work_uses_weekday_window_and_capacity_leaves_overflow(self):
        plan = make_plan([task('a', minutes=60), task('b', minutes=60)], '2026-11-16', 60, NOW)
        self.assertEqual(plan['blocks'][0]['start'], '08:00')
        self.assertEqual(plan['blocks'][0]['end'], '09:00')
        self.assertEqual(len(plan['blocks']), 1)
        self.assertEqual(plan['unscheduled'][0]['id'], 'b')

    def test_weekend_work_is_not_scheduled_but_personal_is(self):
        plan = make_plan([task(), task('p', 'personal')], '2026-11-21', 240, NOW)
        self.assertEqual([b['id'] for b in plan['blocks']], ['p'])
        self.assertEqual(plan['blocks'][0]['start'], '06:00')
        self.assertEqual(plan['unscheduled'][0]['id'], 'a')

    def test_weekday_personal_does_not_overlap_work_or_sleep(self):
        plan = make_plan([task('p', 'personal', 180)], '2026-11-16', 240, NOW)
        self.assertEqual(plan['blocks'][0]['start'], '17:00')
        self.assertEqual(plan['blocks'][0]['end'], '20:00')

    def test_no_blocks_in_the_past(self):
        now = datetime(2026, 11, 16, 16, 45, tzinfo=TZ)
        plan = make_plan([task()], '2026-11-16', 240, now)
        self.assertEqual(plan['blocks'], [])
        self.assertEqual(len(plan['unscheduled']), 1)
        with self.assertRaises(ValueError):
            make_plan([task()], '2026-11-15', 240, now)

    def test_rejects_duplicate_tasks_and_invalid_inputs(self):
        for tasks in ([task(), task()], [task(minutes=0)], [task(kind='unknown')], [task(minutes=True)]):
            with self.subTest(tasks=tasks), self.assertRaises(ValueError):
                make_plan(tasks, '2026-11-16', 240, NOW)

    def test_save_uses_separate_folder_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = make_plan([task()], '2026-11-16', 240, NOW)
            first = save_plan(root, plan)
            second = save_plan(root, plan)
            self.assertEqual(first.parent, root / 'Bej Plans')
            self.assertNotEqual(first, second)
            self.assertIn('08:00–08:30', first.read_text(encoding='utf-8'))
            self.assertIn('Projects.md', first.read_text(encoding='utf-8'))
            self.assertEqual(scan_vault(root)['tasks'], [])


if __name__ == '__main__':
    unittest.main()
