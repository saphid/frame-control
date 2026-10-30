"""Transport retries may not bypass certificate, content or permanent errors."""
import importlib.util
from pathlib import Path
import ssl
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

# GI belongs to the offline tooling environment; these transport tests do not
# parse variants or verify signatures. Other supported hosts can skip them.
try:
    import gi  # noqa: F401
except ImportError:
    gi = None


@unittest.skipIf(gi is None, 'Offline Flatpak fetch tool requires Python GI')
class FetchTransport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / 'scripts/framey-fetch-syncthing-flatpak.py'
        spec = importlib.util.spec_from_file_location('flatpak_fetch', path)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def response(self, data):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = data
        return response

    def test_transient_tls_handshake_timeout_retries_then_preserves_bytes(self):
        with patch.object(self.module.urllib.request, 'urlopen', side_effect=[
            urllib.error.URLError(TimeoutError('handshake timeout')), self.response(b'payload')
        ]) as fetch, patch.object(self.module.time, 'sleep'):
            self.assertEqual(self.module.download('https://example.test/object', 8), b'payload')
            self.assertEqual(fetch.call_count, 2)

    def test_certificate_rejection_fails_without_retry(self):
        with patch.object(self.module.urllib.request, 'urlopen', side_effect=urllib.error.URLError(
            ssl.SSLCertVerificationError('certificate rejected')
        )) as fetch, self.assertRaisesRegex(RuntimeError, 'certificate rejected'):
            self.module.download('https://example.test/object', 8)
        self.assertEqual(fetch.call_count, 1)

    def test_missing_object_fails_without_retry(self):
        with patch.object(self.module.urllib.request, 'urlopen', side_effect=urllib.error.HTTPError(
            'https://example.test/object', 404, 'missing', {}, None
        )) as fetch, self.assertRaisesRegex(RuntimeError, '404'):
            self.module.download('https://example.test/object', 8)
        self.assertEqual(fetch.call_count, 1)

    def test_repeated_timeout_stops_after_three_attempts_with_public_url(self):
        with patch.object(self.module.urllib.request, 'urlopen', side_effect=TimeoutError('timed out')) as fetch, patch.object(self.module.time, 'sleep'), self.assertRaisesRegex(RuntimeError, 'https://example.test/object'):
            self.module.download('https://example.test/object', 8)
        self.assertEqual(fetch.call_count, 3)

    def test_oversized_content_is_refused_without_retry(self):
        with patch.object(self.module.urllib.request, 'urlopen', return_value=self.response(b'oversized')) as fetch, self.assertRaisesRegex(ValueError, 'exceeds bound'):
            self.module.download('https://example.test/object', 8)
        self.assertEqual(fetch.call_count, 1)


if __name__ == '__main__':
    unittest.main()
