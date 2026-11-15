import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from web_bridge import WebBridge


class Secrets:
    def __init__(self): self.data = {}
    def get(self, key): return self.data.get(key)
    def set(self, key, value): self.data[key] = value


class WebBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.secrets = Secrets()
        self.bridge = WebBridge(self.root, self.secrets)
        self.identity = 'a' * 32
        self.origin = 'chrome-extension://' + self.identity

    def test_pairing_is_one_use_exact_origin_persistent_and_revocable(self):
        pairing = self.bridge.begin(self.identity)
        with self.assertRaises(ValueError): self.bridge.pair('https://example.com', pairing['pairingCode'])
        token = self.bridge.pair(self.origin, pairing['pairingCode'])['captureToken']
        with self.assertRaises(ValueError): self.bridge.pair(self.origin, pairing['pairingCode'])
        again = WebBridge(self.root, self.secrets)
        self.assertTrue(again.authorize(self.origin, 'Bearer ' + token))
        self.assertFalse(again.authorize('chrome-extension://' + 'b' * 32, 'Bearer ' + token))
        self.assertFalse(again.authorize(self.origin, 'Bearer workspace-token'))
        self.assertFalse(WebBridge(self.root / 'other', self.secrets).authorize(self.origin, 'Bearer ' + token))
        again.revoke()
        self.assertFalse(again.authorize(self.origin, 'Bearer ' + token))

    def test_expired_and_repeated_wrong_codes_cannot_pair(self):
        with patch('web_bridge.time.time', return_value=0):
            code = self.bridge.begin(self.identity)['pairingCode']
        with self.assertRaises(ValueError): self.bridge.pair(self.origin, code)
        code = self.bridge.begin(self.identity)['pairingCode']
        for _ in range(5):
            with self.assertRaises(ValueError): self.bridge.pair(self.origin, 'wrong')
        with self.assertRaises(ValueError): self.bridge.pair(self.origin, code)

    def test_new_pairing_revokes_old_access_and_uses_a_new_preview_scope(self):
        token = self.bridge.pair(self.origin, self.bridge.begin(self.identity)['pairingCode'])['captureToken']
        scope = self.bridge.authorize(self.origin, 'Bearer ' + token)
        code = self.bridge.begin(self.identity)['pairingCode']
        self.assertFalse(self.bridge.authorize(self.origin, 'Bearer ' + token))
        second = self.bridge.pair(self.origin, code)['captureToken']
        self.assertNotEqual(scope, self.bridge.authorize(self.origin, 'Bearer ' + second))
