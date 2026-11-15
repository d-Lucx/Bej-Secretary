"""Windows Credential Manager storage, including chunked MSAL caches."""
import json
import uuid


class WindowsSecrets:
    def __init__(self):
        from keyring.backends.Windows import WinVaultKeyring
        self.backend = WinVaultKeyring()

    def get(self, name):
        value = self.backend.get_password('Bej-Secretary', name)
        if not value or not value.startswith('{"bejChunks":'):
            return value
        meta = json.loads(value)
        parts = [self.backend.get_password('Bej-Secretary', f"{name}:{meta['generation']}:{i}") for i in range(meta['bejChunks'])]
        if any(part is None for part in parts):
            raise ValueError('The saved credential cache is incomplete. Sign in again.')
        return ''.join(parts)

    def set(self, name, value):
        old = self.backend.get_password('Bej-Secretary', name)
        old_meta = json.loads(old) if old and old.startswith('{"bejChunks":') else None
        if len(value.encode('utf-16-le')) <= 4000:
            self.backend.set_password('Bej-Secretary', name, value)
        else:
            generation = uuid.uuid4().hex
            parts = [value[i:i + 1000] for i in range(0, len(value), 1000)]
            for i, part in enumerate(parts):
                self.backend.set_password('Bej-Secretary', f'{name}:{generation}:{i}', part)
            self.backend.set_password('Bej-Secretary', name, json.dumps({'bejChunks': len(parts), 'generation': generation}, separators=(',', ':')))
        if old_meta:
            for i in range(old_meta['bejChunks']):
                try:
                    self.backend.delete_password('Bej-Secretary', f"{name}:{old_meta['generation']}:{i}")
                except Exception:
                    pass
