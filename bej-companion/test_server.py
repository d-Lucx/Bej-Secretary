import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from server import create_app
from planner import MANILA


class ServiceTests(unittest.TestCase):
    def test_plan_reminder_switch_off_and_completed_source_guard(self):
        from state import LocalStore
        store = LocalStore(self.root / '.bej-local')
        task = self.client.get('/api/tasks', headers=self.headers).json()['tasks'][0]
        day = (datetime.now(MANILA) + timedelta(days=1)).date().isoformat()
        plan = {'id': 'switch-plan', 'date': day, 'blocks': [{**task, 'category': 'personal', 'start': '08:00', 'end': '08:30'}]}
        store.put_plan(plan)
        store.arm(plan, 'desktop')
        response = self.client.get('/api/plans/switch-plan/reminders', headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['desktop']['pending'], 1)
        response = self.client.post('/api/reminders/disarm', json={'planId': plan['id'], 'channel': 'desktop'}, headers=self.headers)
        self.assertEqual(response.json()['canceled'], 1)
        self.assertEqual(self.client.get('/api/plans/switch-plan/reminders', headers=self.headers).json()['desktop']['pending'], 0)
        (self.vault / 'Notes.md').write_text('# Work\n- [x] Build Bej\n', encoding='utf-8')
        response = self.client.post('/api/reminders/arm', json={'planId': plan['id'], 'channel': 'desktop'}, headers=self.headers)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertTrue(all(r['state'] != 'pending' for r in store.reminders()))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.vault = self.root / 'vault'
        self.vault.mkdir()
        (self.vault / 'Notes.md').write_text('# Work\n- [ ] Build Bej\n', encoding='utf-8')
        self.app = create_app(self.root, 'test-secret', self.vault)
        self.client = TestClient(self.app, base_url='http://127.0.0.1:8766')
        self.headers = {'Authorization': 'Bearer test-secret'}

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def test_private_data_requires_auth_and_rejects_foreign_origins_and_hosts(self):
        self.assertEqual(self.client.get('/api/tasks').status_code, 401)
        foreign = {**self.headers, 'Origin': 'https://example.com'}
        self.assertEqual(self.client.get('/api/tasks', headers=foreign).status_code, 403)
        self.assertEqual(self.client.get('/api/tasks', headers={**self.headers, 'Host': 'evil.test:8766'}).status_code, 403)
        self.assertEqual(self.client.get('/api/tasks', headers=self.headers).status_code, 200)

    def test_plan_can_only_reference_real_tasks_and_known_drafts(self):
        tomorrow = (datetime.now(MANILA) + timedelta(days=1)).date().isoformat()
        body = {'date': tomorrow, 'capacity': 120, 'tasks': [{'id': 'invented', 'category': 'work', 'minutes': 30, 'fingerprint': 'x'}]}
        self.assertEqual(self.client.post('/api/plan', json=body, headers=self.headers).status_code, 409)
        self.assertEqual(self.client.post('/api/plans/save', json={'planId': 'invented'}, headers=self.headers).status_code, 404)

    def test_save_is_explicit_and_does_not_change_source(self):
        before = (self.vault / 'Notes.md').read_bytes()
        task = self.client.get('/api/tasks', headers=self.headers).json()['tasks'][0]
        day = (datetime.now(MANILA) + timedelta(days=1)).date().isoformat()
        body = {'date': day, 'capacity': 120, 'tasks': [{'id': task['id'], 'fingerprint': task['fingerprint'], 'category': 'personal', 'minutes': 30}]}
        response = self.client.post('/api/plan', json=body, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse((self.vault / 'Bej Plans').exists())
        saved = self.client.post('/api/plans/save', json={'planId': response.json()['id']}, headers=self.headers)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertTrue(Path(saved.json()['path']).is_file())
        again = self.client.post('/api/plans/save', json={'planId': response.json()['id']}, headers=self.headers)
        self.assertEqual(again.json()['path'], saved.json()['path'])
        self.assertEqual((self.vault / 'Notes.md').read_bytes(), before)

    def test_stale_notes_require_rescan_and_estimates_are_strict(self):
        task = self.client.get('/api/tasks', headers=self.headers).json()['tasks'][0]
        (self.vault / 'Notes.md').write_text('# Changed\n- [ ] Build Bej\n', encoding='utf-8')
        body = {'date': (datetime.now(MANILA) + timedelta(days=1)).date().isoformat(), 'capacity': 120,
                'tasks': [{'id': task['id'], 'fingerprint': task['fingerprint'], 'category': 'personal', 'minutes': 30}]}
        self.assertEqual(self.client.post('/api/plan', json=body, headers=self.headers).status_code, 409)
        body['tasks'][0]['minutes'] = True
        self.assertEqual(self.client.post('/api/plan', json=body, headers=self.headers).status_code, 422)

    def test_validation_never_echoes_a_submitted_credential(self):
        secret = 'short-SECRET'
        response = self.client.post('/api/discord/credential', json={'token': secret}, headers=self.headers)
        self.assertEqual(response.status_code, 422)
        self.assertNotIn(secret, response.text)

    def test_scan_reports_which_oversized_note_was_skipped(self):
        (self.vault / 'TooLarge.md').write_text('x' * 2_000_001, encoding='utf-8')
        result = self.client.get('/api/tasks', headers=self.headers).json()
        self.assertEqual(result['warnings'], ['Skipped oversized note: TooLarge.md'])


if __name__ == '__main__':
    unittest.main()
