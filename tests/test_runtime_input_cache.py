"""Restored/downloaded bytes must satisfy the same immutable input pins."""
import hashlib
import io
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch

MODULE = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/framey-cache-runtime-inputs.py'))
cache_input = MODULE['cache_input']


class RuntimeInputCache(unittest.TestCase):
    def test_download_is_verified_then_reused_without_network(self):
        data = b'exact published input'
        digest = hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory() as folder, patch('urllib.request.urlopen', return_value=io.BytesIO(data)) as fetch:
            path = Path(folder) / 'cache' / 'loader'
            self.assertFalse(cache_input(path, 'https://example.test/input', digest, 100)['cacheHit'])
            self.assertEqual(path.read_bytes(), data)
            self.assertTrue(cache_input(path, 'https://example.test/input', digest, 100)['cacheHit'])
            fetch.assert_called_once()

    def test_corrupt_restore_fails_without_silent_refetch(self):
        with tempfile.TemporaryDirectory() as folder, patch('urllib.request.urlopen') as fetch:
            path = Path(folder) / 'loader'
            path.write_bytes(b'corrupt cache entry')
            with self.assertRaisesRegex(ValueError, 'digest mismatch'):
                cache_input(path, 'https://example.test/input', hashlib.sha256(b'expected').hexdigest(), 100)
            fetch.assert_not_called()
            self.assertEqual(path.read_bytes(), b'corrupt cache entry')

    def test_invalid_or_oversized_download_never_becomes_cached_input(self):
        for data, digest, limit in [(b'wrong', hashlib.sha256(b'expected').hexdigest(), 100),
                                    (b'too large', hashlib.sha256(b'too large').hexdigest(), 3)]:
            with self.subTest(data=data), tempfile.TemporaryDirectory() as folder:
                with patch('urllib.request.urlopen', return_value=io.BytesIO(data)):
                    path = Path(folder) / 'loader'
                    with self.assertRaisesRegex(ValueError, 'size or digest mismatch'):
                        cache_input(path, 'https://example.test/input', digest, limit)
                    self.assertFalse(path.exists())
                    self.assertEqual(list(Path(folder).iterdir()), [])

    def test_download_failure_is_preserved_without_partial_cache(self):
        with tempfile.TemporaryDirectory() as folder, patch('urllib.request.urlopen', side_effect=TimeoutError('gateway')):
            path = Path(folder) / 'loader'
            with self.assertRaisesRegex(TimeoutError, 'gateway'):
                cache_input(path, 'https://example.test/input', '0' * 64, 100)
            self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
