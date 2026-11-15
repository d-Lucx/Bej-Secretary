import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from captures import CaptureError, CaptureStore


WEBM = b'\x1a\x45\xdf\xa3fixture'


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = CaptureStore(self.root)

    def test_streamed_capture_normalizes_mime_and_roundtrips(self):
        record = self.store.save('microphone', [WEBM[:2], WEBM[2:]], 'audio/webm;codecs=opus')
        self.assertEqual(record['kind'], 'microphone')
        self.assertEqual(record['mime'], 'audio/webm')
        self.assertEqual(record['bytes'], len(WEBM))
        self.assertEqual(record['filename'], record['id'] + '.webm')
        path, mime = self.store.file(record['id'])
        self.assertEqual(path.read_bytes(), WEBM)
        self.assertEqual(mime, 'audio/webm')
        self.assertEqual(path.parent, self.root / 'captures')
        self.assertEqual(self.store.list(), [record])
        self.assertEqual(CaptureStore(self.root).list(), [record])

    def test_screen_capture_accepts_video_webm(self):
        record = self.store.save('screen', [WEBM], 'video/webm; codecs=vp9,opus')
        self.assertEqual(self.store.file(record['id'])[1], 'video/webm')

    def test_invalid_kind_mime_or_header_leaves_no_files(self):
        for kind, mime, chunks in [
            ('camera', 'video/webm', [WEBM]), ('screen', 'video/mp4', [WEBM]),
            ('microphone', 'video/webm', [WEBM]), ('screen', 'video/webm', []),
            ('screen', 'video/webm', [b'not webm']), ('screen', 'video/webm', ['bad']),
        ]:
            with self.subTest(kind=kind, mime=mime):
                with self.assertRaises(CaptureError):
                    self.store.save(kind, chunks, mime)
                self.assertEqual(list((self.root / 'captures').iterdir()), [])

    def test_oversize_stream_stops_without_retaining_partial_data(self):
        def chunks():
            yield WEBM
            for _ in range(51):
                yield b'x' * (1024 * 1024)
        with self.assertRaises(CaptureError):
            self.store.save('screen', chunks(), 'video/webm')
        self.assertEqual(list((self.root / 'captures').iterdir()), [])

    def test_failed_source_cleans_temporary_files(self):
        def chunks():
            yield WEBM
            raise RuntimeError('device disconnected')
        with self.assertRaises(RuntimeError):
            self.store.save('screen', chunks(), 'video/webm')
        self.assertEqual(list((self.root / 'captures').iterdir()), [])

    def test_traversal_and_unknown_ids_do_not_touch_other_files(self):
        sentinel = self.root / 'keep.webm'
        sentinel.write_bytes(WEBM)
        for identifier in ['../keep', '..\\keep', '/keep', 'a' * 32, '']:
            with self.subTest(identifier=identifier):
                with self.assertRaises(CaptureError):
                    self.store.file(identifier)
                with self.assertRaises(CaptureError):
                    self.store.delete(identifier)
        self.assertEqual(sentinel.read_bytes(), WEBM)

    def test_list_orders_newest_first_and_ignores_unowned_files(self):
        first = self.store.save('screen', [WEBM], 'video/webm')
        second = self.store.save('microphone', [WEBM], 'audio/webm')
        (self.root / 'captures' / 'unrelated.json').write_text('{}')
        (self.root / 'captures' / 'unrelated.webm').write_bytes(WEBM)
        self.assertEqual([entry['id'] for entry in self.store.list()], [second['id'], first['id']])

    def test_metadata_cannot_redirect_file_or_delete(self):
        record = self.store.save('screen', [WEBM], 'video/webm')
        sentinel = self.root / 'keep.webm'
        sentinel.write_bytes(WEBM)
        metadata = self.root / 'captures' / (record['id'] + '.json')
        record['filename'] = '../keep.webm'
        metadata.write_text(json.dumps(record))
        self.assertEqual(self.store.list(), [])
        with self.assertRaises(CaptureError):
            self.store.delete(record['id'])
        self.assertEqual(sentinel.read_bytes(), WEBM)

    def test_explicit_delete_removes_only_selected_capture(self):
        first = self.store.save('screen', [WEBM], 'video/webm')
        second = self.store.save('screen', [WEBM], 'video/webm')
        self.assertEqual(self.store.delete(first['id']), {'deleted': True, 'id': first['id']})
        self.assertEqual(self.store.list(), [second])
        self.assertEqual({p.name for p in (self.root / 'captures').iterdir()},
                         {second['id'] + '.webm', second['id'] + '.json'})

    def test_linked_storage_or_capture_is_rejected(self):
        outside = self.root / 'outside'
        outside.mkdir()
        linked = self.root / 'linked'
        try:
            linked.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest('Creating symlinks requires Windows developer mode')
        with self.assertRaises(CaptureError):
            CaptureStore(linked)
        (outside / 'captures').symlink_to(self.root / 'captures', target_is_directory=True)
        with self.assertRaises(CaptureError):
            CaptureStore(outside)
        record = self.store.save('screen', [WEBM], 'video/webm')
        path, _ = self.store.file(record['id'])
        path.unlink()
        sentinel = self.root / 'keep.webm'
        sentinel.write_bytes(WEBM)
        path.symlink_to(sentinel)
        with self.assertRaises(CaptureError):
            self.store.delete(record['id'])
        self.assertEqual(sentinel.read_bytes(), WEBM)

    @unittest.skipUnless(os.name == 'nt', 'Windows junction check')
    def test_junction_storage_is_rejected(self):
        outside = self.root / 'junction-target'
        outside.mkdir()
        junction = self.root / 'junction'
        created = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(outside)],
                                 capture_output=True, check=False)
        if created.returncode:
            self.skipTest('Junction creation is unavailable')
        with self.assertRaises(CaptureError):
            CaptureStore(junction)
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
