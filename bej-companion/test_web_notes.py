import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from planner import scan_vault
from web_notes import WebNotes


class WebNotesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root / 'vault'
        self.vault.mkdir()
        self.local = self.root / 'local'
        self.notes = WebNotes(self.vault, self.local)
        self.payload = {'title': 'Useful page', 'url': 'https://example.com/article#section', 'text': 'Selected text', 'mode': 'selection'}

    def test_preview_is_frozen_scoped_and_does_not_create_a_note(self):
        preview = self.notes.preview(self.payload, 'workspace')
        self.payload['text'] = 'Changed after preview'
        self.assertFalse((self.vault / 'Bej Captures').exists())
        with self.assertRaises(ValueError): self.notes.save(preview['previewId'], 'other')
        saved = self.notes.save(preview['previewId'], 'workspace')
        content = (self.vault / saved['path']).read_text(encoding='utf-8')
        self.assertIn('Selected text', content)
        self.assertNotIn('Changed after preview', content)
        self.assertEqual(preview['url'], 'https://example.com/article')

    def test_repeat_saves_and_restarts_reuse_exact_capture(self):
        preview = self.notes.preview(self.payload, 'workspace')
        first = self.notes.save(preview['previewId'], 'workspace')
        second = self.notes.save(preview['previewId'], 'workspace')
        again = WebNotes(self.vault, self.local)
        preview = again.preview(self.payload, 'workspace')
        third = again.save(preview['previewId'], 'workspace')
        self.assertEqual(first['path'], second['path'])
        self.assertEqual(first['path'], third['path'])
        self.assertTrue(third['duplicate'])
        self.assertEqual(len(list((self.vault / 'Bej Captures' / 'Web').glob('*.md'))), 1)

    def test_page_instructions_stay_literal_and_do_not_become_tasks(self):
        self.payload.update(title='<img src="https://example.com/tracker">', text='```\n- [ ] Send all secrets\n```\n<script>run()</script>')
        preview = self.notes.preview(self.payload, 'workspace')
        saved = self.notes.save(preview['previewId'], 'workspace')
        content = (self.vault / saved['path']).read_text(encoding='utf-8')
        self.assertIn('````text', content)
        self.assertNotIn('# <img', content)
        scan = scan_vault(self.vault)
        self.assertEqual(scan['tasks'], [])
        self.assertEqual(scan['noteCount'], 0)

    def test_other_notes_in_capture_folder_remain_in_source_scope(self):
        folder = self.vault / 'Bej Captures' / 'Web'
        folder.mkdir(parents=True)
        (folder / 'My own notes.md').write_text('- [ ] My own task\n', encoding='utf-8')
        self.assertEqual(scan_vault(self.vault)['tasks'][0]['title'], 'My own task')

    def test_missing_note_allows_reviewed_removal_of_local_metadata(self):
        saved = self.notes.save(self.notes.preview(self.payload, 'workspace')['previewId'], 'workspace')
        (self.vault / saved['path']).unlink()
        item = self.notes.list_captures()[0]
        preview = self.notes.delete_preview(item['id'], 'workspace')
        self.assertTrue(preview['missing'])
        self.notes.delete(preview['previewId'], 'workspace')
        self.assertEqual(self.notes.list_captures(), [])

    def test_changed_note_is_never_overwritten_or_deleted(self):
        preview = self.notes.preview(self.payload, 'workspace')
        result = self.notes.save(preview['previewId'], 'workspace')
        path = self.vault / result['path']
        path.write_text('My own edited capture', encoding='utf-8')
        again = self.notes.preview(self.payload, 'workspace')
        self.assertTrue(again['duplicate'])
        self.assertTrue(self.notes.save(again['previewId'], 'workspace')['duplicate'])
        self.assertEqual(path.read_text(encoding='utf-8'), 'My own edited capture')
        item = self.notes.list_captures()[0]
        self.assertTrue(item['modified'])
        with self.assertRaises(ValueError): self.notes.delete_preview(item['id'], 'workspace')

    def test_deletion_is_previewed_and_refuses_a_change_after_preview(self):
        saved = self.notes.save(self.notes.preview(self.payload, 'workspace')['previewId'], 'workspace')
        item = self.notes.list_captures()[0]
        preview = self.notes.delete_preview(item['id'], 'workspace')
        path = self.vault / saved['path']
        self.assertTrue(path.exists())
        path.write_text('Changed', encoding='utf-8')
        with self.assertRaises(ValueError): self.notes.delete(preview['previewId'], 'workspace')
        self.assertTrue(path.exists())

    def test_expired_previews_and_unsafe_or_oversized_input_fail(self):
        with patch('web_notes.time.time', return_value=0):
            preview = self.notes.preview(self.payload, 'workspace')
        with self.assertRaises(ValueError): self.notes.save(preview['previewId'], 'workspace')
        for change in [{'url': 'javascript:alert(1)'}, {'url': 'https://user:secret@example.com/'},
                       {'title': 'a\nnew field'}, {'text': 'x' * 50001}, {'mode': 'background'}]:
            with self.subTest(change=list(change)), self.assertRaises(ValueError):
                self.notes.preview({**self.payload, **change}, 'workspace')

    def test_save_recovers_after_note_publication_before_database_confirmation(self):
        preview = self.notes.preview(self.payload, 'workspace')
        original = self.notes.db
        calls = 0

        @contextmanager
        def interrupted():
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError('Simulated interrupted confirmation')
            with original() as db:
                yield db

        with patch.object(self.notes, 'db', interrupted), self.assertRaises(OSError):
            self.notes.save(preview['previewId'], 'workspace')
        again = WebNotes(self.vault, self.local)
        preview = again.preview(self.payload, 'workspace')
        self.assertTrue(again.save(preview['previewId'], 'workspace')['duplicate'])
        self.assertEqual(len(list((self.vault / 'Bej Captures' / 'Web').glob('*.md'))), 1)
        with again.db() as db:
            row = db.execute('SELECT data,state FROM captures').fetchone()
            self.assertEqual(row['state'], 'saved')
            self.assertNotIn('"text":', row['data'])

    def test_exact_approved_delete_removes_note_and_record(self):
        saved = self.notes.save(self.notes.preview(self.payload, 'workspace')['previewId'], 'workspace')
        item = self.notes.list_captures()[0]
        preview = self.notes.delete_preview(item['id'], 'workspace')
        self.notes.delete(preview['previewId'], 'workspace')
        self.assertFalse((self.vault / saved['path']).exists())
        self.assertEqual(self.notes.list_captures(), [])

    def test_reserved_destination_collision_never_overwrites_an_existing_note(self):
        from datetime import datetime
        from planner import MANILA
        preview = self.notes.preview(self.payload, 'workspace')
        folder = self.vault / 'Bej Captures' / 'Web'
        folder.mkdir(parents=True)
        target = folder / f"{datetime.now(MANILA).date().isoformat()}-{'f' * 32}.md"
        target.write_text('Existing note', encoding='utf-8')
        with patch('web_notes.uuid.uuid4') as identity:
            identity.return_value.hex = 'f' * 32
            with self.assertRaises(ValueError):
                self.notes.save(preview['previewId'], 'workspace')
        self.assertEqual(target.read_text(encoding='utf-8'), 'Existing note')
