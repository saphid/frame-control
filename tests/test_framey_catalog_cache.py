"""Exact catalog cache bytes gate transport tests, including restored caches."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('catalog_cache', ROOT / 'scripts/framey-cache-catalog.py')
cache_script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache_script)


class CatalogCache(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.responses = {}
        cls.requests = []

        class Fixture(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                cls.requests.append(self.path)
                data = cls.responses.get(self.path)
                if data is None:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.write(data)

        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
        cls.addClassCleanup(cls.server.server_close)
        cls.addClassCleanup(cls.server.shutdown)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.cache = self.root / 'cache'
        self.fixtures = self.root / 'fixtures'
        self.cache.mkdir()
        self.fixtures.mkdir()
        self.responses.clear()
        self.requests.clear()
        self.data = b'Archive bytes are verified without importing plugin code.\n'
        self.digest = hashlib.sha256(self.data).hexdigest()
        self.record = dict(id=777, version='1.2.3', sha256=self.digest)
        self.target = self.cache / (self.digest + '.zip')
        self.route = '/versions/' + self.digest + '.zip'
        patcher = patch.object(cache_script, 'CDN', f'http://127.0.0.1:{self.server.server_port}/versions/')
        patcher.start()
        self.addCleanup(patcher.stop)

    def prepare(self):
        return cache_script.archive(self.record, self.cache, self.fixtures)

    def test_cold_download_checks_hash_and_publishes_readable_bytes(self):
        self.responses[self.route] = self.data
        result = self.prepare()
        self.assertEqual(self.target.read_bytes(), self.data)
        self.assertEqual(result, dict(self.record, bytes=len(self.data), source='cdn'))
        self.assertEqual(self.requests, [self.route])
        self.assertEqual(list(self.cache.iterdir()), [self.target])

    def test_wrong_download_is_not_published_and_owned_temp_is_removed(self):
        self.responses[self.route] = b'different archive'
        with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
            self.prepare()
        self.assertEqual(list(self.cache.iterdir()), [])

    def test_oversized_download_is_not_published(self):
        self.responses[self.route] = self.data
        with patch.object(cache_script, 'MAX_ARCHIVE', len(self.data) - 1):
            with self.assertRaisesRegex(ValueError, 'size limit'):
                self.prepare()
        self.assertEqual(list(self.cache.iterdir()), [])

    def test_cache_hit_is_verified_without_network(self):
        self.target.write_bytes(self.data)
        self.assertEqual(self.prepare()['source'], 'cache')
        self.assertEqual(self.requests, [])

    def test_corrupt_restored_cache_fails_and_preserves_existing_file(self):
        self.target.write_bytes(b'corrupt cached bytes')
        with self.assertRaisesRegex(ValueError, 'cached archive SHA-256 mismatch'):
            self.prepare()
        self.assertEqual(self.target.read_bytes(), b'corrupt cached bytes')
        self.assertEqual(self.requests, [])

    def test_vendored_fixture_is_hash_checked_before_caching(self):
        fixture = self.fixtures / '777.zip'
        fixture.write_bytes(b'wrong fixture')
        with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
            self.prepare()
        self.assertFalse(self.target.exists())
        fixture.write_bytes(self.data)
        self.assertEqual(self.prepare()['source'], 'fixture')
        self.assertEqual(self.target.read_bytes(), self.data)
        self.assertEqual(self.requests, [])

    def test_cli_reports_all_results_and_returns_failure_for_a_bad_pin(self):
        self.target.write_bytes(self.data)
        bad = dict(id=778, version='0.1', sha256='a' * 64)
        (self.cache / (bad['sha256'] + '.zip')).write_bytes(b'wrong')
        catalog = self.root / 'catalog.json'
        catalog.write_text(json.dumps({'plugins': [self.record, bad]}))
        output = self.root / 'evidence/cache.json'
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/framey-cache-catalog.py'),
                                 '--catalog', str(catalog), '--cache', str(self.cache),
                                 '--output', str(output)], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(output.read_text())
        self.assertFalse(report['success'])
        self.assertFalse(report['pluginCodeExecuted'])
        self.assertEqual(report['catalogSha256'], hashlib.sha256(catalog.read_bytes()).hexdigest())
        self.assertEqual([r['id'] for r in report['records']], [777, 778])
        self.assertEqual(report['records'][0]['source'], 'cache')
        self.assertEqual(report['records'][1]['error'], 'cached archive SHA-256 mismatch')


if __name__ == '__main__':
    unittest.main()
