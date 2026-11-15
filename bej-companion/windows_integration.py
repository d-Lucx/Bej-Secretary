"""Local Windows notification and explicitly enabled login startup adapters."""
from __future__ import annotations

import base64
import json
import os
import stat
import subprocess
import tempfile
import threading
from pathlib import Path


def _ordinary(path: Path) -> None:
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Linked Windows integration paths are not supported.')


class WindowsIntegration:
    def __init__(self, project: Path, local_dir: Path, *, runner=None, startup_dir: Path | None = None):
        self.project = Path(project).absolute()
        self.local_dir = Path(local_dir).absolute()
        self._runner = runner or subprocess.run
        self._injected_runner = runner is not None
        appdata = os.environ.get('APPDATA')
        self.startup_dir = (Path(startup_dir).absolute() if startup_dir is not None else
                            Path(appdata) / 'Microsoft/Windows/Start Menu/Programs/Startup' if appdata else None)
        self._lock = threading.Lock()

    def notify(self, title: str, message: str) -> dict:
        if (not isinstance(title, str) or not title.strip() or len(title) > 63
                or any(char in title for char in '\r\n\x00')
                or not isinstance(message, str) or not message.strip() or len(message) > 1000 or '\x00' in message):
            raise ValueError('Provide a notification title of 1–63 characters and message of 1–1000 characters.')
        script = self.project / 'bej-companion' / 'notify.ps1'
        powershell = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        try:
            _ordinary(script)
            if not script.is_file() or (not self._injected_runner and (os.name != 'nt' or not powershell.is_file())):
                raise ValueError('The desktop notification could not be shown.')
            payload = base64.b64encode(json.dumps({'title': title, 'message': message}, ensure_ascii=False).encode('utf-8')).decode('ascii')
            arguments = [str(powershell), '-NoProfile', '-NonInteractive', '-STA', '-WindowStyle', 'Hidden',
                         '-ExecutionPolicy', 'Bypass', '-File', str(script), '-PayloadBase64', payload]
            result = self._runner(arguments, shell=False, check=False, capture_output=True,
                                  timeout=20, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode != 0:
                raise ValueError('The desktop notification could not be shown.')
        except (OSError, subprocess.SubprocessError):
            raise ValueError('The desktop notification could not be shown.') from None
        return {'messageId': 'desktop'}

    def _command(self, *, validate: bool = False) -> bytes:
        executable = self.local_dir / 'venv' / 'Scripts' / 'pythonw.exe'
        server = self.project / 'bej-companion' / 'server.py'
        for path in (executable, server, self.project):
            if any(char in str(path) for char in '%^&|<>"\r\n\x00'):
                raise ValueError('The project path contains unsupported Windows startup characters.')
            _ordinary(path)
        if validate and (not executable.is_file() or not server.is_file()):
            raise ValueError('Install the local Python runtime before enabling login startup.')
        return (f'@echo off\r\nrem Bej-Secretary managed startup\r\nsetlocal DisableDelayedExpansion\r\nchcp 65001 >nul\r\n'
                f'cd /d "{self.project}"\r\nstart "" "{executable}" "{server}" --no-open\r\n').encode('utf-8')

    def _target(self) -> Path:
        if self.startup_dir is None:
            raise ValueError('The Windows user Startup folder is unavailable.')
        target = self.startup_dir / 'Bej-Secretary.cmd'
        _ordinary(target)
        if not self.startup_dir.is_dir():
            raise ValueError('The Windows user Startup folder is unavailable.')
        return target

    def status(self) -> dict:
        try:
            target = self._target()
            enabled = target.is_file() and target.read_bytes() == self._command()
            return {'startupEnabled': enabled}
        except (OSError, ValueError):
            return {'startupEnabled': False}

    def enable_startup(self, enabled: bool) -> dict:
        if type(enabled) is not bool:
            raise ValueError('Startup enabled must be true or false.')
        with self._lock:
            temporary = None
            try:
                target = self._target()
                command = self._command(validate=enabled)
                if target.exists() and (not target.is_file() or target.read_bytes() != command):
                    raise ValueError('The startup filename is occupied by an unmanaged file.')
                if not enabled:
                    target.unlink(missing_ok=True)
                elif not target.exists():
                    descriptor, temporary = tempfile.mkstemp(prefix='.bej-startup-', suffix='.tmp', dir=self.startup_dir)
                    with os.fdopen(descriptor, 'wb') as handle:
                        handle.write(command)
                        handle.flush()
                        os.fsync(handle.fileno())
                    _ordinary(target)
                    # Windows rename fails if another process created this filename.
                    if os.name == 'nt':
                        os.rename(temporary, target)
                    else:
                        os.link(temporary, target)
                return {'enabled': enabled}
            except OSError:
                raise ValueError('The login startup setting could not be saved.') from None
            finally:
                if temporary:
                    try:
                        Path(temporary).unlink(missing_ok=True)
                    except OSError:
                        pass
