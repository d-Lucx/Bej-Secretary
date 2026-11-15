import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from server import create_app


class Secrets:
    def __init__(self): self.values = {}
    def get(self, key): return self.values.get(key)
    def set(self, key, value): self.values[key] = value


class WebRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root / 'vault'
        self.vault.mkdir()
        self.client = TestClient(create_app(self.root, 'workspace-token', self.vault, credential_store=Secrets(), enable_worker=False), base_url='http://127.0.0.1:8766')
        self.addCleanup(self.client.close)
        self.workspace = {'Authorization': 'Bearer workspace-token'}
        self.origin = 'chrome-extension://' + 'a' * 32
        self.capture = {'title': 'Page', 'url': 'https://example.com/', 'text': 'Text', 'mode': 'selection'}

    def pair(self):
        response = self.client.post('/api/web/pairing', headers=self.workspace, json={'extensionId': 'a' * 32})
        self.assertEqual(response.status_code, 200, response.text)
        code = response.json()['pairingCode']
        response = self.client.post('/extension/web/pair', headers={'Origin': self.origin}, json={'pairingCode': code})
        self.assertEqual(response.status_code, 200, response.text)
        return {'Origin': self.origin, 'Authorization': 'Bearer ' + response.json()['captureToken']}

    def test_scoped_round_trip_and_workspace_isolation(self):
        extension = self.pair()
        preview = self.client.post('/extension/web/preview', headers=extension, json=self.capture)
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(preview.headers['access-control-allow-origin'], self.origin)
        self.assertFalse((self.vault / 'Bej Captures').exists())
        saved = self.client.post('/extension/web/save', headers=extension, json={'previewId': preview.json()['previewId']})
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertTrue((self.vault / saved.json()['path']).is_file())
        for path in ['/api/tasks', '/api/web/captures', '/api/outlook/sync']:
            response = self.client.post(path, headers=extension, json={})
            self.assertEqual(response.status_code, 403, path)
        self.assertEqual(self.client.get('/api/web/captures', headers={'Authorization': extension['Authorization']}).status_code, 401)
        self.assertEqual(self.client.post('/extension/web/preview', headers={'Origin': self.origin, **self.workspace}, json=self.capture).status_code, 401)

    def test_preflight_is_exact_origin_post_only_and_cannot_open_other_routes(self):
        self.client.post('/api/web/pairing', headers=self.workspace, json={'extensionId': 'a' * 32})
        headers = {'Origin': self.origin, 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'content-type'}
        response = self.client.options('/extension/web/pair', headers=headers)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers['access-control-allow-origin'], self.origin)
        for origin in ['https://example.com', 'null', 'chrome-extension://' + 'b' * 32, '']:
            response = self.client.options('/extension/web/pair', headers={**headers, 'Origin': origin})
            self.assertEqual(response.status_code, 403)
            self.assertNotIn('access-control-allow-origin', response.headers)
        self.assertEqual(self.client.options('/api/tasks', headers=headers).status_code, 403)
        self.assertEqual(self.client.options('/extension/web/install', headers=headers).status_code, 404)

    def test_revoke_invalidates_token_and_old_frozen_previews(self):
        headers = self.pair()
        preview = self.client.post('/extension/web/preview', headers=headers, json=self.capture).json()
        self.client.post('/api/web/revoke', headers=self.workspace, json={})
        self.assertEqual(self.client.post('/extension/web/save', headers=headers, json={'previewId': preview['previewId']}).status_code, 403)
        new_headers = self.pair()
        self.assertEqual(self.client.post('/extension/web/save', headers=new_headers, json={'previewId': preview['previewId']}).status_code, 400)

    def test_streamed_requests_are_bounded_and_errors_do_not_echo_contents(self):
        extension = self.pair()
        response = self.client.post('/extension/web/preview', headers=extension, content=iter([b'x' * 200000, b'x' * 100000]))
        self.assertEqual(response.status_code, 413, response.text)
        secret = 'PRIVATE-CAPTURE-TEXT'
        response = self.client.post('/extension/web/pair', headers={'Origin': self.origin}, json={'pairingCode': secret, 'extra': secret})
        self.assertNotIn(secret, response.text)
        self.assertEqual(self.client.post('/extension/web/preview', json=self.capture).status_code, 403)

    def test_workspace_supports_unicode_capture_and_immutable_save(self):
        response = self.client.post('/api/web/preview', headers=self.workspace, json={**self.capture, 'text': 'あ' * 30000})
        self.assertEqual(response.status_code, 200, response.text)
        preview = response.json()
        response = self.client.post('/api/web/save', headers=self.workspace, json={'previewId': preview['previewId'], 'text': 'replace'})
        self.assertEqual(response.status_code, 422)
