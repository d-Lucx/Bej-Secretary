"""Exact, short-lived approvals for narrowly scoped source task edits.

Approvals live only in this process and are consumed once a write is attempted.
Vault text is data, never instructions. Backups are local original byte copies.
"""
from __future__ import annotations

import hashlib
import os
import re
import stat
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath

_TASK = re.compile(r'^(?P<prefix>[^\S\r\n]*[-*+][^\S\r\n]+\[)(?P<check> )(?P<middle>\][^\S\r\n]+)(?P<title>.*?)(?P<tail>[^\S\r\n]*)$')
_BLOCKED = {'.git', '.obsidian', '.copilot', 'bej plans'}


def _ordinary(path: Path) -> None:
    """Reject links and Windows reparse points, including junctions."""
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            raise ValueError('The source or storage path could not be inspected.') from None
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Linked source or storage paths are not supported.')


class SourceEditor:
    def __init__(self, vault: Path, local_dir: Path):
        self.vault = Path(vault).absolute()
        self.local_dir = Path(local_dir).absolute()
        self._previews: dict[str, dict] = {}
        self._lock = threading.Lock()
        _ordinary(self.vault)
        if not self.vault.is_dir():
            raise ValueError('The configured vault is not a folder.')

    def _source(self, source: str) -> Path:
        if not isinstance(source, str) or not source or '\\' in source or ':' in source or '\x00' in source:
            raise ValueError('Choose an ordinary Markdown source inside the vault.')
        parts = source.split('/')
        if (PureWindowsPath(source).is_absolute() or source.startswith('/')
                or any(part in ('', '.', '..') or part.casefold() in _BLOCKED
                       or part.endswith((' ', '.')) for part in parts)):
            raise ValueError('Choose an ordinary Markdown source inside the vault.')
        path = self.vault.joinpath(*parts)
        _ordinary(path)
        try:
            if path.suffix.casefold() != '.md' or not path.is_file() or not path.resolve().is_relative_to(self.vault.resolve()):
                raise ValueError('The source note is unavailable or outside the supported scope.')
        except OSError:
            raise ValueError('The source note could not be inspected.') from None
        return path

    @staticmethod
    def _read(path: Path) -> bytes:
        try:
            if path.stat().st_size > 2_000_000:
                raise ValueError('The source note is too large.')
            return path.read_bytes()
        except OSError:
            raise ValueError('The source note could not be read.') from None

    def preview(self, task: dict, *, text: str | None = None,
                completed: bool | None = None) -> dict:
        if not isinstance(task, dict):
            raise ValueError('Select a valid scanned task.')
        if text is not None and (not isinstance(text, str) or not text.strip() or len(text) > 1000
                                 or any(char in text for char in '\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029\x00')):
            raise ValueError('Task text must be one nonblank line of at most 1000 characters.')
        if completed is not None and type(completed) is not bool:
            raise ValueError('Task completion must be true or false.')
        path = self._source(task.get('source'))
        raw = self._read(path)
        if hashlib.sha256(raw).hexdigest() != task.get('fingerprint'):
            raise ValueError('The source changed. Scan again before previewing an edit.')
        try:
            decoded = raw.decode('utf-8-sig')
        except UnicodeError:
            raise ValueError('The source note must be UTF-8.') from None
        lines = decoded.splitlines(keepends=True)
        number = task.get('line')
        if type(number) is not int or not 1 <= number <= len(lines):
            raise ValueError('The scanned task line is unavailable.')
        original = lines[number - 1]
        before = original.rstrip('\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029')
        ending = original[len(before):]
        match = _TASK.fullmatch(before)
        if not match or not match['title'].strip() or match['title'].strip() != task.get('title'):
            raise ValueError('The source line no longer matches the scanned unchecked task.')
        expected_id = hashlib.sha256(f"{task['source']}\0{number}\0{task['title']}".encode()).hexdigest()[:24]
        if expected_id != task.get('id'):
            raise ValueError('The source task identity does not match the scan.')
        after = (match['prefix'] + ('x' if completed is True else ' ') + match['middle']
                 + (text if text is not None else match['title']) + match['tail'])
        if after == before:
            raise ValueError('Choose a change before creating an approval preview.')
        lines[number - 1] = after + ending
        updated = (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'') + ''.join(lines).encode('utf-8')
        expires = time.time() + 15 * 60
        preview_id = uuid.uuid4().hex
        public = {'previewId': preview_id, 'source': task['source'], 'line': number,
                  'before': before, 'after': after,
                  'expiresAt': datetime.fromtimestamp(expires, timezone.utc).isoformat()}
        with self._lock:
            now = time.time()
            self._previews = {key: value for key, value in self._previews.items() if value['expires'] > now}
            self._previews[preview_id] = {'public': public.copy(), 'raw': raw,
                                          'updated': updated, 'expires': expires}
        return public

    def apply(self, preview_id: str) -> dict:
        with self._lock:
            if not isinstance(preview_id, str):
                raise ValueError('The edit approval is unknown or already used.')
            preview = self._previews.pop(preview_id, None)
            if preview is None:
                raise ValueError('The edit approval is unknown or already used.')
            if time.time() >= preview['expires']:
                raise ValueError('The edit approval expired. Create a new preview.')
            public = preview['public']
            path = self._source(public['source'])
            if self._read(path) != preview['raw']:
                raise ValueError('The source changed. Create a new preview before applying.')
            backup = self.local_dir / 'backups' / f'{preview_id}.md'
            temporary = None
            try:
                _ordinary(backup)
                backup.parent.mkdir(parents=True, exist_ok=True)
                _ordinary(backup)
                with backup.open('xb') as handle:
                    handle.write(preview['raw'])
                    handle.flush()
                    os.fsync(handle.fileno())
                descriptor, temporary = tempfile.mkstemp(prefix='.bej-edit-', suffix='.tmp', dir=path.parent)
                with os.fdopen(descriptor, 'wb') as handle:
                    handle.write(preview['updated'])
                    handle.flush()
                    os.fsync(handle.fileno())
                # Recheck immediately before replacement, after backup and staging I/O.
                if self._source(public['source']) != path or self._read(path) != preview['raw']:
                    raise ValueError('The source changed. Create a new preview before applying.')
                os.replace(temporary, path)
                return {'source': public['source'], 'line': public['line'],
                        'backupPath': str(backup), 'applied': True}
            except OSError:
                raise ValueError('The edit could not be saved. The approval has been consumed.') from None
            finally:
                if temporary is not None:
                    try:
                        Path(temporary).unlink(missing_ok=True)
                    except OSError:
                        pass
