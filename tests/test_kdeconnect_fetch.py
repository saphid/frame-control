"""The iOS Frame bundle must recover transient pinned package downloads."""
import hashlib
import http.client
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import urllib.error
import io


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location('kdeconnect_fetch', ROOT / 'frame/kdeconnect/fetch.py')
fetch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch)


class VerifiedDownload(unittest.TestCase):
    def test_remote_disconnect_retries_then_checks_hash(self):
        data = b'pinned package'
        digest = hashlib.sha256(data).hexdigest()
        with patch.object(fetch.urllib.request, 'urlopen', side_effect=[
                http.client.RemoteDisconnected('closed'), io.BytesIO(data)]) as open_url, \
                patch.object(fetch.time, 'sleep') as sleep:
            self.assertEqual(fetch.download_verified('https://example.invalid/package', digest), data)
        self.assertEqual(open_url.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_permanent_http_error_and_wrong_hash_fail_closed(self):
        url = 'https://example.invalid/package'
        missing = urllib.error.HTTPError(url, 404, 'missing', {}, None)
        with patch.object(fetch.urllib.request, 'urlopen', side_effect=missing) as open_url, \
                patch.object(fetch.time, 'sleep') as sleep:
            with self.assertRaises(urllib.error.HTTPError):
                fetch.download_verified(url, '0' * 64)
        open_url.assert_called_once()
        sleep.assert_not_called()
        with patch.object(fetch.urllib.request, 'urlopen', return_value=io.BytesIO(b'changed')) as open_url:
            with self.assertRaisesRegex(SystemExit, 'checksum mismatch'):
                fetch.download_verified(url, '0' * 64)
        open_url.assert_called_once()

    def test_exhausted_transient_error_is_not_silenced(self):
        with patch.object(fetch.urllib.request, 'urlopen', side_effect=http.client.RemoteDisconnected('closed')) as open_url, \
                patch.object(fetch.time, 'sleep') as sleep:
            with self.assertRaises(http.client.RemoteDisconnected):
                fetch.download_verified('https://example.invalid/package', '0' * 64)
        self.assertEqual(open_url.call_count, 3)
        self.assertEqual(sleep.call_count, 2)


if __name__ == '__main__':
    unittest.main()
