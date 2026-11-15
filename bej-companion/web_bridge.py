"""One-use pairing and project-scoped capture-only browser credentials."""
import hashlib
import json
import re
import secrets
import threading
import time
from pathlib import Path


class WebBridge:
    def __init__(self, project, credential_store):
        self.store = credential_store
        digest = hashlib.sha256(str(Path(project).resolve()).casefold().encode()).hexdigest()[:24]
        self.key = 'web-capture-' + digest
        self.pending = None
        self.lock = threading.RLock()

    def _record(self):
        raw = self.store.get(self.key)
        if not raw:
            return {}
        try:
            value = json.loads(raw)
            if (not re.fullmatch(r'[a-p]{32}', value['extensionId']) or not isinstance(value['token'], str)
                    or len(value['token']) < 40):
                raise ValueError()
            return value
        except (ValueError, KeyError, TypeError):
            raise ValueError('Browser credential storage needs a new pairing.') from None

    def begin(self, extension_id):
        if not isinstance(extension_id, str) or not re.fullmatch(r'[a-p]{32}', extension_id):
            raise ValueError('Enter the exact 32-letter Chrome/Edge extension ID (a–p).')
        with self.lock:
            self.store.set(self.key, '')  # Replacement explicitly revokes the old connection now.
            self.pending = {'extensionId': extension_id, 'code': secrets.token_urlsafe(18),
                            'expiresAt': time.time() + 300, 'attempts': 0}
            return {'pairingCode': self.pending['code'], 'expiresAt': self.pending['expiresAt']}

    def allowed_origin(self, origin, *, pairing=False):
        with self.lock:
            if pairing:
                record = self.pending if self.pending and self.pending['expiresAt'] > time.time() else {}
            else:
                record = self._record()
            return bool(record and origin == 'chrome-extension://' + record['extensionId'])

    def pair(self, origin, code):
        with self.lock:
            if not self.allowed_origin(origin, pairing=True):
                raise ValueError('Pairing expired or the extension is not approved. Generate a fresh code in Bej.')
            self.pending['attempts'] += 1
            if not isinstance(code, str) or not code.isascii() or not secrets.compare_digest(code, self.pending['code']):
                if self.pending['attempts'] >= 5:
                    self.pending = None
                raise ValueError('Pairing code is invalid. Generate a fresh code in Bej if needed.')
            token = secrets.token_urlsafe(32)
            self.store.set(self.key, json.dumps({'extensionId': self.pending['extensionId'], 'token': token}))
            self.pending = None
            return {'captureToken': token}

    def authorize(self, origin, authorization):
        with self.lock:
            record = self._record()
            if (not record or not (authorization or '').isascii() or origin != 'chrome-extension://' + record['extensionId']
                    or not secrets.compare_digest(authorization or '', 'Bearer ' + record['token'])):
                return None
            return 'extension:' + hashlib.sha256(record['token'].encode()).hexdigest()

    def revoke(self):
        with self.lock:
            self.store.set(self.key, '')
            self.pending = None

    def status(self):
        with self.lock:
            record = self._record()
            pending = self.pending if self.pending and self.pending['expiresAt'] > time.time() else None
            return {'extensionId': record.get('extensionId') or (pending['extensionId'] if pending else None),
                    'paired': bool(record), **({'pairingExpiresAt': pending['expiresAt']} if pending else {})}
