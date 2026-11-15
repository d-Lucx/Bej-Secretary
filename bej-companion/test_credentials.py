import unittest
from credentials import WindowsSecrets


class FakeBackend:
    def __init__(self): self.data = {}
    def get_password(self, service, name): return self.data.get((service, name))
    def set_password(self, service, name, value):
        if len(value.encode('utf-16-le')) > 5120: raise ValueError('Native credential limit')
        self.data[service, name] = value
    def delete_password(self, service, name): self.data.pop((service, name), None)


class CredentialTests(unittest.TestCase):
    def test_large_msal_cache_roundtrips_and_old_chunks_are_removed(self):
        store = WindowsSecrets.__new__(WindowsSecrets)
        store.backend = FakeBackend()
        cache = 'private-cache-value' * 1500
        store.set('outlook', cache)
        self.assertEqual(store.get('outlook'), cache)
        self.assertGreater(len(store.backend.data), 1)
        store.set('outlook', 'replacement')
        self.assertEqual(store.get('outlook'), 'replacement')
        self.assertEqual(len(store.backend.data), 1)

    def test_incomplete_chunk_cache_is_not_returned(self):
        store = WindowsSecrets.__new__(WindowsSecrets)
        store.backend = FakeBackend()
        store.set('outlook', 'cache' * 4000)
        key = next(key for key in store.backend.data if key[1].endswith(':0'))
        del store.backend.data[key]
        with self.assertRaises(ValueError): store.get('outlook')


if __name__ == '__main__': unittest.main()
