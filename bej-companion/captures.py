"""Local storage for explicitly uploaded recordings. Never acquires device media."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
import threading
import uuid


class CaptureError(ValueError):
    """Safe validation failure for capture API callers."""


class CaptureStore:
    MAX_BYTES = 50 * 1024 * 1024
    WEBM_HEADER = b'\x1a\x45\xdf\xa3'
    MIME_BY_KIND = {'microphone': 'audio/webm', 'screen': 'video/webm'}

    def __init__(self, local_dir: Path):
        self.directory = Path(os.path.abspath(local_dir)) / 'captures'
        self._lock = threading.RLock()
        self._check_path(self.directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._check_storage()

    @staticmethod
    def _check_path(path):
        # Inspect every ancestor before resolving paths: resolve() would conceal links.
        for entry in (path, *path.parents):
            try:
                info = entry.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise CaptureError('Capture storage cannot contain links or junctions.')

    def _check_storage(self):
        self._check_path(self.directory)
        if not self.directory.is_dir():
            raise CaptureError('Capture storage is unavailable.')

    @staticmethod
    def _check_id(capture_id):
        if not isinstance(capture_id, str) or re.fullmatch(r'[0-9a-f]{32}', capture_id) is None:
            raise CaptureError('Invalid capture ID.')

    @staticmethod
    def _created_at():
        return datetime.now(timezone.utc).isoformat()

    def save(self, kind: str, chunks, mime: str):
        expected_mime = self.MIME_BY_KIND.get(kind) if isinstance(kind, str) else None
        normalized_mime = mime.split(';', 1)[0].strip().lower() if isinstance(mime, str) else ''
        if expected_mime is None or normalized_mime != expected_mime:
            raise CaptureError('Choose a microphone audio/WebM or screen video/WebM capture.')
        with self._lock:
            self._check_storage()
            capture_id = uuid.uuid4().hex
            data_path = self.directory / (capture_id + '.webm')
            metadata_path = self.directory / (capture_id + '.json')
            data_temp = self.directory / (capture_id + '.webm.tmp')
            metadata_temp = self.directory / (capture_id + '.json.tmp')
            created_data = False
            try:
                size = 0
                header = b''
                with data_temp.open('xb') as output:
                    for chunk in chunks:
                        if not isinstance(chunk, bytes):
                            raise CaptureError('Capture uploads must contain binary data.')
                        size += len(chunk)
                        if size > self.MAX_BYTES:
                            raise CaptureError('Capture exceeds the 50 MiB upload limit.')
                        if len(header) < 4:
                            header += chunk[:4 - len(header)]
                            if len(header) == 4 and header != self.WEBM_HEADER:
                                raise CaptureError('Capture must be a WebM recording.')
                        output.write(chunk)
                    if header != self.WEBM_HEADER:
                        raise CaptureError('Capture is empty or is not a WebM recording.')
                    output.flush()
                    os.fsync(output.fileno())
                record = {'id': capture_id, 'kind': kind, 'createdAt': self._created_at(),
                          'bytes': size, 'mime': normalized_mime, 'filename': data_path.name}
                with metadata_temp.open('x', encoding='utf-8') as output:
                    json.dump(record, output, ensure_ascii=True)
                    output.flush()
                    os.fsync(output.fileno())
                self._check_storage()
                os.replace(data_temp, data_path)
                created_data = True
                os.replace(metadata_temp, metadata_path)
                return record
            except BaseException:
                # Only these exact files were created by this save operation.
                for temporary in (data_temp, metadata_temp):
                    temporary.unlink(missing_ok=True)
                if created_data:
                    data_path.unlink(missing_ok=True)
                raise

    def _read(self, capture_id):
        self._check_id(capture_id)
        self._check_storage()
        metadata_path = self.directory / (capture_id + '.json')
        data_path = self.directory / (capture_id + '.webm')
        self._check_path(metadata_path)
        self._check_path(data_path)
        try:
            if not metadata_path.is_file() or not data_path.is_file():
                raise CaptureError('Capture was not found.')
            if metadata_path.stat().st_size > 4096:
                raise CaptureError('Capture metadata is invalid.')
            record = json.loads(metadata_path.read_text(encoding='utf-8'))
            if not isinstance(record, dict):
                raise CaptureError('Capture metadata is invalid.')
            kind = record.get('kind')
            if (record.get('id') != capture_id or record.get('filename') != data_path.name
                    or not isinstance(kind, str) or kind not in self.MIME_BY_KIND
                    or record.get('mime') != self.MIME_BY_KIND[kind]
                    or type(record.get('bytes')) is not int
                    or not 4 <= record['bytes'] <= self.MAX_BYTES
                    or data_path.stat().st_size != record['bytes']):
                raise CaptureError('Capture metadata is invalid.')
            created_at = datetime.fromisoformat(record['createdAt'])
            if created_at.tzinfo is None:
                raise CaptureError('Capture metadata is invalid.')
            with data_path.open('rb') as media:
                if media.read(4) != self.WEBM_HEADER:
                    raise CaptureError('Capture data is invalid.')
            # Return the documented metadata only, even if an edited JSON has extra keys.
            return {key: record[key] for key in ('id', 'kind', 'createdAt', 'bytes', 'mime', 'filename')}
        except (OSError, ValueError, TypeError, KeyError):
            raise CaptureError('Capture is missing or its local data is invalid.') from None

    def list(self):
        with self._lock:
            self._check_storage()
            records = []
            for path in self.directory.glob('*.json'):
                try:
                    records.append(self._read(path.stem))
                except CaptureError:
                    continue
            return sorted(records, key=lambda entry: (entry['createdAt'], entry['id']), reverse=True)

    def file(self, capture_id: str):
        with self._lock:
            record = self._read(capture_id)
            return self.directory / record['filename'], record['mime']

    def delete(self, capture_id: str):
        with self._lock:
            self._check_id(capture_id)
            self._check_storage()
            data = self.directory / (capture_id + '.webm')
            metadata = self.directory / (capture_id + '.json')
            self._check_path(data)
            self._check_path(metadata)
            if not data.exists() and not metadata.exists():
                raise CaptureError('Capture was not found.')
            if data.exists() and metadata.exists():
                self._read(capture_id)  # Refuse altered metadata before deleting a complete record.
            # Retry safely after an interrupted deletion; never follow metadata paths.
            data.unlink(missing_ok=True)
            metadata.unlink(missing_ok=True)
            return {'deleted': True, 'id': capture_id}
