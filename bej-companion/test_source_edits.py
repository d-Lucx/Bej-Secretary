import hashlib
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from planner import scan_vault
from source_edits import SourceEditor


class SourceEditorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root / 'vault'
        self.vault.mkdir()
        self.local = self.root / 'local'
        self.note = self.vault / 'tasks.md'
        self.original = b'\xef\xbb\xbf# Tasks\r\n  * [ ] Original task  \r\n- [ ] Other task\r\n'
        self.note.write_bytes(self.original)
        self.task = scan_vault(self.vault)['tasks'][0]
        self.editor = SourceEditor(self.vault, self.local)

    def test_preview_has_exact_lines_and_never_writes(self):
        preview = self.editor.preview(self.task, text='Revised task', completed=True)
        self.assertEqual(preview['before'], '  * [ ] Original task  ')
        self.assertEqual(preview['after'], '  * [x] Revised task  ')
        self.assertEqual(self.note.read_bytes(), self.original)
        self.assertFalse(self.local.exists())

    def test_apply_preserves_bom_crlf_and_unrelated_bytes_with_backup(self):
        preview = self.editor.preview(self.task, text='Revised task', completed=True)
        result = self.editor.apply(preview['previewId'])
        self.assertTrue(result['applied'])
        self.assertEqual(self.note.read_bytes(), self.original.replace(b'[ ] Original task', b'[x] Revised task'))
        self.assertEqual(Path(result['backupPath']).read_bytes(), self.original)
        self.assertTrue(Path(result['backupPath']).is_relative_to(self.local / 'backups'))

    def test_stale_scan_is_rejected(self):
        self.note.write_bytes(self.original + b'new line\r\n')
        with self.assertRaises(ValueError):
            self.editor.preview(self.task, completed=True)

    def test_same_line_concurrent_edit_rejects_approval_without_backup(self):
        preview = self.editor.preview(self.task, completed=True)
        changed = self.original.replace(b'Original task', b'Concurrent task')
        self.note.write_bytes(changed)
        with self.assertRaises(ValueError):
            self.editor.apply(preview['previewId'])
        self.assertEqual(self.note.read_bytes(), changed)
        self.assertFalse(self.local.exists())

    def test_expired_preview_cannot_write(self):
        preview = self.editor.preview(self.task, completed=True)
        with patch('source_edits.time.time', return_value=10**12):
            with self.assertRaises(ValueError):
                self.editor.apply(preview['previewId'])
        self.assertEqual(self.note.read_bytes(), self.original)

    def test_preview_is_single_use(self):
        preview = self.editor.preview(self.task, completed=True)
        self.editor.apply(preview['previewId'])
        with self.assertRaises(ValueError):
            self.editor.apply(preview['previewId'])

    def test_unknown_approval_is_rejected(self):
        with self.assertRaises(ValueError):
            self.editor.apply('../unknown')

    def test_reparse_point_is_rejected_without_host_link_privileges(self):
        with patch('source_edits.Path.lstat', return_value=SimpleNamespace(st_mode=0, st_file_attributes=0x400)):
            with self.assertRaises(ValueError):
                self.editor.preview(self.task, completed=True)

    def test_noop_is_rejected(self):
        with self.assertRaises(ValueError):
            self.editor.preview(self.task)
        with self.assertRaises(ValueError):
            self.editor.preview(self.task, completed=False)

    def test_backup_failure_cannot_change_source_and_consumes_approval(self):
        preview = self.editor.preview(self.task, completed=True)
        self.local.write_text('not a directory', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.editor.apply(preview['previewId'])
        self.assertEqual(self.note.read_bytes(), self.original)
        with self.assertRaises(ValueError):
            self.editor.apply(preview['previewId'])

    def test_other_line_concurrent_change_rejects_approval(self):
        preview = self.editor.preview(self.task, completed=True)
        self.note.write_bytes(self.original.replace(b'Other task', b'Changed elsewhere'))
        with self.assertRaises(ValueError):
            self.editor.apply(preview['previewId'])

    def test_escaped_and_system_paths_are_rejected(self):
        for source in ('../outside.md', '/outside.md', 'C:\\outside.md', 'folder/../tasks.md', '.obsidian/tasks.md', '.git/tasks.md', 'Bej Plans/tasks.md', 'tasks.md:stream'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.editor.preview({**self.task, 'source': source}, completed=True)

    def test_invalid_text_and_completed_are_rejected(self):
        for text in ('', ' ', 'one\ntwo', 'one\rtwo', 'one\u2028two', 'x' * 1001, 123):
            with self.subTest(text=str(text)[:20]), self.assertRaises(ValueError):
                self.editor.preview(self.task, text=text)
        with self.assertRaises(ValueError):
            self.editor.preview(self.task, completed='true')

    def test_task_identity_must_match(self):
        for override in ({'title': 'Other task'}, {'id': 'forged'}, {'line': True}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                self.editor.preview({**self.task, **override}, completed=True)

    def test_lf_and_no_final_newline_preserved(self):
        raw = b'- [ ] first\n\t+ [ ] last'
        self.note.write_bytes(raw)
        task = scan_vault(self.vault)['tasks'][1]
        preview = self.editor.preview(task, text='updated')
        self.editor.apply(preview['previewId'])
        self.assertEqual(self.note.read_bytes(), b'- [ ] first\n\t+ [ ] updated')

    def test_symlink_file_and_directory_rejected(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'tasks.md').write_bytes(self.original)
        try:
            (self.vault / 'link').symlink_to(outside, target_is_directory=True)
            (self.vault / 'linked.md').symlink_to(outside / 'tasks.md')
        except OSError:
            self.skipTest('Symlink creation is unavailable on this host')
        for source in ('link/tasks.md', 'linked.md'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.editor.preview({**self.task, 'source': source}, completed=True)


if __name__ == '__main__':
    unittest.main()
