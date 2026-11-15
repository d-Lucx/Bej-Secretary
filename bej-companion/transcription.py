"""Explicit, offline-only transcription of retained local recordings.

Only prepare_model may download the fixed tiny model. Recordings and transcripts
are local data and are never interpreted as commands or instructions.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile
import threading
import uuid


class LocalTranscriber:
    MAX_BYTES = 50 * 1024 * 1024
    REPOSITORY = 'Systran/faster-whisper-tiny'
    MODEL_FILES = ['config.json', 'model.bin', 'tokenizer.json', 'vocabulary.*', 'preprocessor_config.json']

    def __init__(self, capture_store, local_dir: Path, *, model_factory=None):
        self.capture_store = capture_store
        self.local_dir = Path(local_dir).absolute()
        self.model_root = self.local_dir / 'whisper-models'
        self.model_factory = model_factory
        self._lock = threading.Lock()

    @staticmethod
    def _id(identifier):
        if not isinstance(identifier, str) or re.fullmatch('[0-9a-f]{32}', identifier) is None:
            raise ValueError('Choose a valid local recording ID.')

    @staticmethod
    def _ordinary(path):
        for entry in (path, *path.parents):
            try:
                info = entry.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Linked transcription storage is not supported.')

    def _capture(self, identifier):
        self._id(identifier)
        path, mime = self.capture_store.file(identifier)
        path = Path(path).absolute()
        expected = Path(self.capture_store.directory).absolute() / (identifier + '.webm')
        self._ordinary(path)
        if path != expected or mime not in ('audio/webm', 'video/webm') or not path.is_file():
            raise ValueError('Choose a retained microphone or screen recording.')
        if not 4 <= path.stat().st_size <= self.MAX_BYTES:
            raise ValueError('The recording must be at most 50 MiB.')
        digest = hashlib.sha256()
        with path.open('rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(chunk)
        return path, digest.hexdigest()

    def _transcript_path(self, identifier):
        self._id(identifier)
        directory = Path(self.capture_store.directory).absolute()
        path = directory / (identifier + '.transcript.json')
        self._ordinary(path)
        return path

    @staticmethod
    def _valid_result(result, identifier):
        if (not isinstance(result, dict) or result.get('captureId') != identifier or result.get('model') != 'tiny'
                or not isinstance(result.get('text'), str) or len(result['text']) > 100000
                or not isinstance(result.get('language'), str) or not 1 <= len(result['language']) <= 32
                or not isinstance(result.get('segments'), list) or len(result['segments']) > 10000
                or not isinstance(result.get('transcriptId'), str)
                or re.fullmatch('[0-9a-f]{32}', result['transcriptId']) is None):
            return False
        for segment in result['segments']:
            if not isinstance(segment, dict) or not isinstance(segment.get('text'), str):
                return False
            start, end = segment.get('start'), segment.get('end')
            if (type(start) not in (float, int) or type(end) not in (float, int)
                    or not math.isfinite(start) or not math.isfinite(end) or not 0 <= start <= end <= 330):
                return False
        return result['text'] == ''.join(segment['text'] for segment in result['segments']).strip()

    def get_transcript(self, identifier):
        self._id(identifier)
        try:
            _, fingerprint = self._capture(identifier)
            path = self._transcript_path(identifier)
            if not path.is_file() or path.stat().st_size > 2_000_000:
                return None
            record = json.loads(path.read_text(encoding='utf-8'))
            if (not isinstance(record, dict) or record.get('fingerprint') != fingerprint
                    or not self._valid_result(record.get('result'), identifier)):
                return None
            return record['result']
        except (OSError, ValueError, TypeError):
            return None

    def delete_transcript(self, identifier):
        self._id(identifier)
        try:
            self._transcript_path(identifier).unlink(missing_ok=True)
            return {'deleted': True, 'captureId': identifier}
        except OSError:
            raise ValueError('The local transcript could not be deleted.') from None

    def prepare_model(self):
        if not self._lock.acquire(blocking=False):
            raise ValueError('Local transcription or model setup is already running.')
        try:
            self._ordinary(self.model_root)
            from huggingface_hub import snapshot_download
            snapshot_download(repo_id=self.REPOSITORY, cache_dir=str(self.model_root), allow_patterns=self.MODEL_FILES)
            return {'model': 'tiny', 'prepared': True}
        except Exception:
            raise ValueError('The local tiny transcription model could not be set up.') from None
        finally:
            self._lock.release()

    def transcribe(self, capture_id: str):
        self._id(capture_id)
        if not self._lock.acquire(blocking=False):
            raise ValueError('Local transcription or model setup is already running.')
        temporary = None
        try:
            path, fingerprint = self._capture(capture_id)
            cached = self.get_transcript(capture_id)
            if cached is not None:
                return cached
            try:
                self._ordinary(self.model_root)
                factory = self.model_factory
                if factory is None:
                    from faster_whisper import WhisperModel
                    factory = WhisperModel
                model = factory('tiny', device='cpu', compute_type='int8', download_root=str(self.model_root), local_files_only=True)
            except Exception:
                raise ValueError('Set up the local tiny transcription model before transcribing.') from None
            try:
                generated, info = model.transcribe(str(path), beam_size=1)
                duration = float(info.duration)
                if not math.isfinite(duration) or not 0 <= duration <= 330:
                    raise ValueError('Recording duration exceeds the supported limit.')
                segments, total = [], 0
                for item in generated:
                    if not isinstance(item.text, str):
                        raise ValueError('Invalid transcript segment.')
                    total += len(item.text)
                    if len(segments) >= 10000 or total > 100000:
                        raise ValueError('Transcript exceeds the supported limit.')
                    segments.append({'start': float(item.start), 'end': float(item.end), 'text': item.text})
                result = {'captureId': capture_id, 'transcriptId': uuid.uuid4().hex,
                          'text': ''.join(item['text'] for item in segments).strip(),
                          'language': info.language, 'segments': segments, 'model': 'tiny'}
                if not self._valid_result(result, capture_id):
                    raise ValueError('Invalid local transcript.')
            except Exception:
                raise ValueError('The local recording could not be transcribed.') from None
            if self._capture(capture_id)[1] != fingerprint:
                raise ValueError('The recording changed during transcription.')
            target = self._transcript_path(capture_id)
            descriptor, temporary = tempfile.mkstemp(prefix='.bej-transcript-', suffix='.tmp', dir=target.parent)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
                json.dump({'fingerprint': fingerprint, 'result': result}, handle, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            self._ordinary(target)
            if self._capture(capture_id)[1] != fingerprint:
                raise ValueError('The recording changed during transcription.')
            os.replace(temporary, target)
            return result
        except OSError:
            raise ValueError('The local recording or transcript could not be accessed.') from None
        finally:
            if temporary is not None:
                try:
                    Path(temporary).unlink(missing_ok=True)
                except OSError:
                    pass
            self._lock.release()
