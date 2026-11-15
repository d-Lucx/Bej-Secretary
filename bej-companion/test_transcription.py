import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from captures import CaptureStore
from transcription import LocalTranscriber


class TranscriptionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.local = Path(self.tmp.name)
        self.store = CaptureStore(self.local)
        self.capture = self.store.save('microphone', [b'\x1a\x45\xdf\xa3fixture'], 'audio/webm')
        self.model = Mock()
        self.model.transcribe.return_value = (iter([SimpleNamespace(start=0.0, end=1.25, text=' Hello'), SimpleNamespace(start=1.25, end=2.0, text=' world.')]), SimpleNamespace(duration=2.0, language='en'))
        self.factory = Mock(return_value=self.model)
        self.transcriber = LocalTranscriber(self.store, self.local, model_factory=self.factory)

    def test_transform_persist_and_cached_load_without_model(self):
        result = self.transcriber.transcribe(self.capture['id'])
        self.assertEqual(result['captureId'], self.capture['id'])
        self.assertEqual(result['model'], 'tiny')
        self.assertEqual(result['text'], 'Hello world.')
        self.assertEqual(result['language'], 'en')
        self.assertEqual(result['segments'], [{'start': 0.0, 'end': 1.25, 'text': ' Hello'}, {'start': 1.25, 'end': 2.0, 'text': ' world.'}])
        kwargs = self.factory.call_args.kwargs
        self.assertEqual(self.factory.call_args.args, ('tiny',))
        self.assertEqual(kwargs['device'], 'cpu')
        self.assertEqual(kwargs['compute_type'], 'int8')
        self.assertTrue(kwargs['local_files_only'])
        self.assertEqual(kwargs['download_root'], str(self.local / 'whisper-models'))
        cached = LocalTranscriber(self.store, self.local, model_factory=Mock(side_effect=AssertionError('no model needed')))
        self.assertEqual(cached.get_transcript(self.capture['id']), result)
        self.assertEqual(self.transcriber.transcribe(self.capture['id']), result)
        self.factory.assert_called_once()

    def test_deletion_is_exact_idempotent_and_capture_survives(self):
        self.transcriber.transcribe(self.capture['id'])
        sentinel = self.local / 'captures' / 'keep.json'
        sentinel.write_text('{}')
        self.assertTrue(self.transcriber.delete_transcript(self.capture['id'])['deleted'])
        self.assertIsNone(self.transcriber.get_transcript(self.capture['id']))
        self.transcriber.delete_transcript(self.capture['id'])
        self.assertTrue(sentinel.exists())
        self.store.file(self.capture['id'])
        with self.assertRaises(ValueError):
            self.transcriber.delete_transcript('../keep')

    def test_changed_capture_does_not_return_cache(self):
        self.transcriber.transcribe(self.capture['id'])
        path, _ = self.store.file(self.capture['id'])
        path.write_bytes(path.read_bytes().replace(b'fixture', b'changed'))
        self.assertIsNone(self.transcriber.get_transcript(self.capture['id']))

    def test_missing_capture_does_not_return_cache(self):
        self.transcriber.transcribe(self.capture['id'])
        self.store.delete(self.capture['id'])
        self.assertIsNone(self.transcriber.get_transcript(self.capture['id']))

    def test_missing_local_model_is_safe_error_and_never_cached(self):
        self.factory.side_effect = OSError('private system path')
        with self.assertRaisesRegex(ValueError, 'Set up the local tiny transcription model'):
            self.transcriber.transcribe(self.capture['id'])
        self.assertIsNone(self.transcriber.get_transcript(self.capture['id']))

    def test_duration_limit_and_invalid_segments_are_rejected(self):
        for duration, segment in [(331, SimpleNamespace(start=0, end=1, text='x')), (2, SimpleNamespace(start=0, end=float('nan'), text='x'))]:
            with self.subTest(duration=duration):
                self.model.transcribe.return_value = (iter([segment]), SimpleNamespace(duration=duration, language='en'))
                with self.assertRaises(ValueError):
                    self.transcriber.transcribe(self.capture['id'])
                self.assertIsNone(self.transcriber.get_transcript(self.capture['id']))

    def test_busy_and_missing_capture_never_start_model(self):
        self.transcriber._lock.acquire()
        try:
            with self.assertRaisesRegex(ValueError, 'already running'):
                self.transcriber.transcribe(self.capture['id'])
        finally:
            self.transcriber._lock.release()
        with self.assertRaises(ValueError):
            self.transcriber.transcribe('f' * 32)
        self.factory.assert_not_called()

    def test_model_generation_failure_is_sanitized(self):
        def broken():
            raise RuntimeError('private system path')
            yield
        self.model.transcribe.return_value = (broken(), SimpleNamespace(duration=2, language='en'))
        with self.assertRaisesRegex(ValueError, '^The local recording could not be transcribed\\.$'):
            self.transcriber.transcribe(self.capture['id'])

    def test_setup_downloads_only_fixed_model_with_explicit_call(self):
        download = Mock()
        with patch.dict('sys.modules', {'huggingface_hub': SimpleNamespace(snapshot_download=download)}):
            self.assertEqual(self.transcriber.prepare_model(), {'model': 'tiny', 'prepared': True})
        self.assertEqual(download.call_args.kwargs['repo_id'], 'Systran/faster-whisper-tiny')
        self.assertEqual(download.call_args.kwargs['cache_dir'], str(self.local / 'whisper-models'))
        self.assertIn('model.bin', download.call_args.kwargs['allow_patterns'])
        self.factory.assert_not_called()

    def test_tampered_cache_is_ignored(self):
        self.transcriber.transcribe(self.capture['id'])
        path = self.local / 'captures' / (self.capture['id'] + '.transcript.json')
        record = json.loads(path.read_text(encoding='utf-8'))
        record['result']['captureId'] = 'f' * 32
        path.write_text(json.dumps(record), encoding='utf-8')
        self.assertIsNone(self.transcriber.get_transcript(self.capture['id']))

    def test_capture_deleted_during_generation_is_not_cached(self):
        def generated():
            self.store.delete(self.capture['id'])
            yield SimpleNamespace(start=0, end=1, text='Hello')
        self.model.transcribe.return_value = (generated(), SimpleNamespace(duration=1, language='en'))
        with self.assertRaises(ValueError):
            self.transcriber.transcribe(self.capture['id'])
        self.assertFalse((self.local / 'captures' / (self.capture['id'] + '.transcript.json')).exists())

    def test_oversize_capture_is_rejected_before_model(self):
        self.transcriber.MAX_BYTES = 5
        with self.assertRaises(ValueError):
            self.transcriber.transcribe(self.capture['id'])
        self.factory.assert_not_called()


if __name__ == '__main__':
    unittest.main()
