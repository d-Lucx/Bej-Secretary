import base64
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from windows_integration import WindowsIntegration


class WindowsIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'Bej project'
        self.local = self.project / '.bej-local'
        (self.local / 'venv' / 'Scripts').mkdir(parents=True)
        (self.local / 'venv' / 'Scripts' / 'pythonw.exe').write_bytes(b'fixture')
        (self.project / 'bej-companion').mkdir()
        (self.project / 'bej-companion' / 'server.py').write_text('# fixture')
        (self.project / 'bej-companion' / 'notify.ps1').write_text('# fixture')
        self.startup = Path(self.temp.name) / 'Startup'
        self.startup.mkdir()
        self.runner = Mock(return_value=subprocess.CompletedProcess([], 0))
        self.integration = WindowsIntegration(self.project, self.local, runner=self.runner, startup_dir=self.startup)

    def test_notification_passes_untrusted_text_only_as_base64_json(self):
        title = 'Task " & $(whoami)'
        message = 'こんにちは\nDo this; exit 1'
        self.assertEqual(self.integration.notify(title, message), {'messageId': 'desktop'})
        args = self.runner.call_args.args[0]
        kwargs = self.runner.call_args.kwargs
        self.assertFalse(kwargs['shell'])
        payload = json.loads(base64.b64decode(args[-1]).decode('utf-8'))
        self.assertEqual(payload, {'title': title, 'message': message})
        self.assertEqual(args[-2], '-PayloadBase64')
        self.assertNotIn(title, args)
        self.assertIn('-WindowStyle', args)

    def test_notification_launch_failures_are_sanitized(self):
        for failure in (OSError('private path'), subprocess.TimeoutExpired(['secret'], 20)):
            self.runner.side_effect = failure
            with self.assertRaisesRegex(ValueError, '^The desktop notification could not be shown\\.$'):
                self.integration.notify('Task', 'Message')
        self.runner.side_effect = None
        self.runner.return_value = subprocess.CompletedProcess([], 1, stderr='secret')
        with self.assertRaises(ValueError):
            self.integration.notify('Task', 'Message')

    def test_invalid_notification_is_never_launched(self):
        for title, message in (('', 'x'), ('x' * 64, 'x'), ('x', ''), ('x', 'x' * 1001), ('x\nnew', 'x'), ('x', 'bad\x00')):
            with self.assertRaises(ValueError):
                self.integration.notify(title, message)
        self.runner.assert_not_called()

    def test_startup_enable_status_disable_preserves_other_files(self):
        other = self.startup / 'Other.cmd'
        other.write_bytes(b'other application')
        self.assertEqual(self.integration.status(), {'startupEnabled': False})
        self.assertEqual(self.integration.enable_startup(True), {'enabled': True})
        content = (self.startup / 'Bej-Secretary.cmd').read_text()
        self.assertIn(str(self.local / 'venv' / 'Scripts' / 'pythonw.exe'), content)
        self.assertIn(str(self.project / 'bej-companion' / 'server.py'), content)
        self.assertIn('--no-open', content)
        self.assertEqual(self.integration.status(), {'startupEnabled': True})
        self.assertEqual(self.integration.enable_startup(False), {'enabled': False})
        self.assertFalse((self.startup / 'Bej-Secretary.cmd').exists())
        self.assertEqual(other.read_bytes(), b'other application')
        self.runner.assert_not_called()

    def test_unowned_startup_entry_is_never_overwritten_or_removed(self):
        target = self.startup / 'Bej-Secretary.cmd'
        target.write_text('@echo This is unrelated')
        for enabled in (True, False):
            with self.assertRaises(ValueError):
                self.integration.enable_startup(enabled)
        self.assertEqual(target.read_text(), '@echo This is unrelated')
        self.assertFalse(self.integration.status()['startupEnabled'])

    def test_startup_rejects_nonboolean_and_missing_target(self):
        with self.assertRaises(ValueError):
            self.integration.enable_startup('yes')
        (self.local / 'venv' / 'Scripts' / 'pythonw.exe').unlink()
        with self.assertRaises(ValueError):
            self.integration.enable_startup(True)
        self.assertFalse((self.startup / 'Bej-Secretary.cmd').exists())

    def test_missing_script_never_launches(self):
        (self.project / 'bej-companion' / 'notify.ps1').unlink()
        with self.assertRaises(ValueError):
            self.integration.notify('Task', 'Message')
        self.runner.assert_not_called()

    def test_startup_reparse_point_is_rejected(self):
        with patch('windows_integration.Path.lstat', return_value=SimpleNamespace(st_mode=0, st_file_attributes=0x400)):
            with self.assertRaises(ValueError):
                self.integration.enable_startup(True)
            self.assertFalse(self.integration.status()['startupEnabled'])

    def test_enable_and_disable_are_idempotent(self):
        self.integration.enable_startup(True)
        target = self.startup / 'Bej-Secretary.cmd'
        original = target.read_bytes()
        self.integration.enable_startup(True)
        self.assertEqual(target.read_bytes(), original)
        self.integration.enable_startup(False)
        self.assertEqual(self.integration.enable_startup(False), {'enabled': False})

    def test_percent_in_startup_command_path_is_rejected(self):
        adapter = WindowsIntegration(self.project / '%PATH%', self.local, runner=self.runner, startup_dir=self.startup)
        with self.assertRaises(ValueError):
            adapter.enable_startup(True)


if __name__ == '__main__':
    unittest.main()
