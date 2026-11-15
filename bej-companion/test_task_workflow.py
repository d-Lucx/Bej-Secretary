import tempfile
import unittest
import json
import hashlib
import time
from unittest.mock import patch
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from planner import MANILA, task_identity
from server import create_app
from state import LocalStore


class Secrets:
    def get(self, name): return None
    def set(self, name, value): pass


class TaskWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root / 'vault'
        self.vault.mkdir()
        self.note = self.vault / 'Work.md'
        self.note.write_text('# Tasks\n- [ ] Review outline 📅 2026-11-16\n', encoding='utf-8')
        self.client = self.client_for_root()
        self.addCleanup(self.client.close)
        self.store = LocalStore(self.root / '.bej-local')
        self.day = (datetime.now(MANILA) + timedelta(days=1)).date().isoformat()

    def client_for_root(self):
        return TestClient(create_app(self.root, 'test', self.vault, credential_store=Secrets(), enable_worker=False),
                          base_url='http://127.0.0.1:8766', headers={'Authorization': 'Bearer test'})

    def tasks(self):
        return self.client.get('/api/tasks').json()['tasks']

    def build(self, task, **changes):
        selection = {'id': task['id'], 'fingerprint': task['fingerprint'], 'category': 'personal', 'minutes': 40,
                     'priority': 'high', 'dueDate': '2026-11-18', **changes}
        return self.client.post('/api/plan', json={'date': self.day, 'capacity': 120, 'tasks': [selection]})

    def test_preferences_survive_line_shift_and_restart_without_source_edit(self):
        task = self.tasks()[0]
        before = self.note.read_bytes()
        response = self.build(task)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.note.read_bytes(), before)
        self.note.write_text('\n' + self.note.read_text(encoding='utf-8'), encoding='utf-8')
        with self.client_for_root() as restarted:
            moved = restarted.get('/api/tasks').json()['tasks'][0]
        self.assertNotEqual(moved['id'], task['id'])
        self.assertEqual(task_identity(moved), task_identity(task))
        self.assertEqual((moved['priority'], moved['dueDate'], moved['category'], moved['minutes']),
                         ('high', '2026-11-18', 'personal', 40))
        rebuilt = self.build(moved).json()
        self.assertEqual(rebuilt['blocks'][0]['id'], response.json()['blocks'][0]['id'])

    def test_invalid_draft_does_not_save_preferences(self):
        task = self.tasks()[0]
        response = self.build(task, dueDate='2026-02-30')
        self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(self.tasks()[0]['dueDate'], '2026-11-16')
        self.assertEqual(self.store.list_plans(), [])

    def test_source_due_date_follows_notes_unless_user_explicitly_overrides_it(self):
        task = self.tasks()[0]
        self.assertEqual(self.build(task, dueDate='2026-11-16').status_code, 200)
        self.note.write_text(self.note.read_text(encoding='utf-8').replace('2026-11-16', '2026-11-17'), encoding='utf-8')
        # A changed title is a new source identity. Ordinary estimates remain private;
        # no old override is attached to unrelated text.
        self.assertEqual(self.tasks()[0]['dueDate'], '2026-11-17')
        self.assertEqual(self.build(self.tasks()[0], dueDate=None).status_code, 200)
        self.assertIsNone(self.tasks()[0]['dueDate'])

    def test_completion_needs_exact_approval_and_immediately_cancels_pending_alerts(self):
        task = self.tasks()[0]
        plan = self.build(task).json()
        self.store.arm(plan, 'desktop')
        progress = self.client.get(f"/api/plans/{plan['id']}/progress").json()
        self.assertEqual(progress['tasks'][task['id']]['status'], 'open')
        preview = self.client.post('/api/source-edits/preview', json={'taskId': task['id'], 'completed': True}).json()
        self.assertIn('- [ ]', self.note.read_text(encoding='utf-8'))
        applied = self.client.post('/api/source-edits/apply', json={'previewId': preview['previewId']})
        self.assertEqual(applied.status_code, 200, applied.text)
        progress = self.client.get(f"/api/plans/{plan['id']}/progress").json()
        self.assertEqual(progress['tasks'][task['id']]['status'], 'completed')
        self.assertEqual(progress['completed'], 1)
        self.assertFalse(any(r['state'] == 'pending' for r in self.store.reminders()))
        self.assertTrue(list((self.root / '.bej-local' / 'backups').glob('*.md')))

    def test_missing_source_is_not_completed_and_progress_uses_current_line(self):
        task = self.tasks()[0]
        plan = self.build(task).json()
        self.note.write_text('\n' + self.note.read_text(encoding='utf-8'), encoding='utf-8')
        progress = self.client.get(f"/api/plans/{plan['id']}/progress").json()
        self.assertEqual(progress['tasks'][task['id']]['task']['line'], 3)
        self.note.unlink()
        progress = self.client.get(f"/api/plans/{plan['id']}/progress").json()
        self.assertEqual(progress['tasks'][task['id']]['status'], 'unavailable')
        self.assertEqual(progress['completed'], 0)

    def test_completed_tasks_are_excluded_from_reflow_and_stale_outlook_approval_is_blocked(self):
        task = self.tasks()[0]
        plan = self.build(task).json()
        self.note.write_text(self.note.read_text(encoding='utf-8').replace('[ ]', '[x]'), encoding='utf-8')
        preview = self.client.post('/api/outlook/preview', json={'planId': plan['id']})
        self.assertEqual(preview.status_code, 409, preview.text)
        reflow = self.client.post('/api/plan/reflow', json={'planId': plan['id'], 'start': '08:00', 'end': '09:00', 'reason': 'Unavailable'})
        self.assertEqual(reflow.status_code, 200, reflow.text)
        self.assertEqual(reflow.json()['blocks'], [])

    def test_progress_cannot_count_duplicate_unchecked_and_checked_occurrences_as_done(self):
        task = self.tasks()[0]
        plan = self.build(task).json()
        self.note.write_text(self.note.read_text(encoding='utf-8') + '- [x] Review outline 📅 2026-11-16\n', encoding='utf-8')
        progress = self.client.get(f"/api/plans/{plan['id']}/progress").json()
        self.assertEqual(progress['completed'], 0)
        self.assertEqual(progress['tasks'][task['id']]['status'], 'open')

    def test_completed_calendar_block_is_not_excluded_as_a_moving_task(self):
        self.note.write_text('# Tasks\n- [ ] First\n- [ ] Second\n', encoding='utf-8')
        tasks = self.tasks()
        selected = [{'id': t['id'], 'fingerprint': t['fingerprint'], 'category': 'personal', 'minutes': 30} for t in tasks]
        plan = self.client.post('/api/plan', json={'date': self.day, 'capacity': 120, 'tasks': selected}).json()
        first, second = plan['blocks']
        self.note.write_text('# Tasks\n- [x] First\n- [ ] Second\n', encoding='utf-8')
        retained = {'start': f"{self.day}T{first['start']}:00+08:00", 'end': f"{self.day}T{first['end']}:00+08:00"}
        with patch('server.OutlookAdapter.planning_busy', return_value={'busy': [retained], 'stale': False, 'lastSyncedAt': None}) as calendar:
            response = self.client.post('/api/plan/reflow', json={'planId': plan['id'], 'start': '08:00', 'end': '09:00', 'reason': 'Unavailable'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(calendar.call_args.args[1], [second['id']])
        self.assertEqual(response.json()['blocks'][0]['start'], first['end'])

    def test_new_draft_reuses_published_legacy_identity_after_older_unpublished_draft(self):
        task = self.tasks()[0]
        block = {**task, 'id': 'older-id', 'category': 'personal', 'minutes': 40, 'start': '06:00', 'end': '06:40'}
        self.store.put_plan({'id': 'old-draft', 'date': self.day, 'blocks': [block], 'unscheduled': []},
                            preferences={task_identity(task): {'planTaskId': 'older-id'}})
        self.store.put_plan({'id': 'published-draft', 'date': self.day, 'blocks': [{**block, 'id': 'published-id'}], 'unscheduled': []})
        key = hashlib.sha256(f'{self.day}\0published-id'.encode()).hexdigest()
        fixed = {'start': f'{self.day}T06:00:00+08:00', 'end': f'{self.day}T06:40:00+08:00', 'eventId': 'event', 'calendarId': 'bej', 'hasAttendees': False}
        state = {'clientId': '12345678-1234-1234-1234-123456789abc', 'accountId': 'test-account', 'calendarId': 'bej',
                 'owned': {key: {'calendarId': 'bej', 'eventId': 'event'}},
                 'days': {self.day: {'timestamp': time.time(), 'busy': [fixed], 'lastSyncedAt': datetime.now(MANILA).isoformat()}}}
        path = self.root / '.bej-local' / 'outlook-state.json'
        path.write_text(json.dumps(state), encoding='utf-8')
        before = path.read_bytes()
        selection = {'id': task['id'], 'fingerprint': task['fingerprint'], 'category': 'personal', 'minutes': 40}
        with self.client_for_root() as restarted:
            response = restarted.post('/api/plan', json={'date': self.day, 'capacity': 120, 'tasks': [selection]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['blocks'][0]['id'], 'published-id')
        self.assertEqual(response.json()['blocks'][0]['start'], '06:00')
        self.assertEqual(path.read_bytes(), before)
