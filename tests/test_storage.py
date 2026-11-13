"""Storage inventory uses only local temporary metadata; no headset connection."""
import sandbox  # noqa: F401
import http.client
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ui'))
import frame_storage as storage
import server


class Storage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.steam = self.home / '.local/share/Steam'
        (self.steam / 'steamapps').mkdir(parents=True)

    def write(self, relative, text):
        path = self.steam / 'steamapps' / relative
        path.write_text(text)
        return path

    def app(self, appid, name, size=None):
        return self.write(f'appmanifest_{appid}.acf', '"AppState" { "appid" "%s" "name" "%s" %s }' %
                          (appid, name, '' if size is None else '"SizeOnDisk" "%s"' % size))

    def inventory(self):
        return storage.inventory(self.home, self.steam)

    def test_multilibrary_dedup_sizes_and_read_only(self):
        extra = self.home / 'other library'
        (extra / 'steamapps').mkdir(parents=True)
        self.write('libraryfolders.vdf', '"libraryfolders" { "0" { "path" "%s" } "1" { "path" "%s" } "2" "%s" }' %
                   (self.steam, extra, extra))
        self.app(1, 'Game', '400')
        self.app(2, 'Proton 10', '100')
        self.app(3, 'Unknown')
        self.app(4, 'Zero', '0')
        self.app(5, 'Bad', '-10')
        (extra / 'steamapps/appmanifest_9.acf').write_text('"AppState" { "appid" "9" "name" "Other" "SizeOnDisk" "200" }')
        before = {p: p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        result = self.inventory()
        self.assertEqual(result['discovery'], 'ok')
        self.assertEqual(len(result['libraries']), 2)
        lib = result['libraries'][0]
        self.assertEqual((lib['gameBytes'], lib['toolBytes'], lib['recordedBytes'], lib['unknownSizes']), (400, 100, 500, 2))
        self.assertEqual([a['bytes'] for a in lib['apps']], [400, 100, 0, None, None])
        self.assertEqual(result['libraries'][1]['recordedBytes'], 200)
        self.assertEqual(before, {p: p.read_bytes() for p in self.home.rglob('*') if p.is_file()})

    def test_partial_and_corrupt_metadata_never_become_empty_success(self):
        self.write('libraryfolders.vdf', '"libraryfolders" {')
        self.app(1, 'Good', '12')
        self.write('appmanifest_2.acf', '"AppState" { "appid" "2"')
        self.write('appmanifest_3.acf', '"AppState" { "appid" "9" }')
        r = self.inventory()
        self.assertEqual(r['discovery'], 'invalid-metadata')
        lib = r['libraries'][0]
        self.assertEqual((lib['state'], lib['recordedBytes'], len(lib['issues'])), ('partial', 12, 2))

    def test_permission_denied_discovery_listing_manifest_and_capacity(self):
        original = storage.read_vdf
        self.app(1, 'Game', '10')
        def read(path):
            if str(path).endswith('appmanifest_1.acf') or str(path).endswith('libraryfolders.vdf'):
                raise PermissionError('denied')
            return original(path)
        with patch.object(storage, 'read_vdf', side_effect=read), patch.object(storage.os, 'statvfs', side_effect=PermissionError(), create=True):
            r = self.inventory()
        self.assertEqual(r['discovery'], 'permission-denied')
        self.assertEqual(r['home']['state'], 'permission-denied')
        self.assertIsNone(r['home']['free'])
        self.assertEqual(r['libraries'][0]['issues'][0]['state'], 'permission-denied')
        with patch.object(storage.os, 'scandir', side_effect=PermissionError()):
            self.assertEqual(self.inventory()['libraries'][0]['state'], 'permission-denied')

    def test_disconnected_library_and_missing_discovery(self):
        r = self.inventory()
        self.assertEqual(r['discovery'], 'missing')
        missing = self.home / 'disconnected'
        self.write('libraryfolders.vdf', '"libraryfolders" { "1" { "path" "%s" } }' % missing)
        lib = self.inventory()['libraries'][1]
        self.assertEqual(lib['state'], 'missing')
        self.assertIsNone(lib['capacity']['total'])

    def test_reserved_capacity_and_shared_filesystem(self):
        stat = SimpleNamespace(f_blocks=100, f_frsize=1024, f_bavail=10, f_bfree=20)
        with patch.object(storage.os, 'statvfs', return_value=stat, create=True):
            r = self.inventory()
        self.assertEqual((r['home']['total'], r['home']['free'], r['home']['used']), (102400, 10240, 81920))
        self.assertEqual(r['home']['filesystem'], r['libraries'][0]['capacity']['filesystem'])

    def test_keyvalues_comments_escaping_and_limits(self):
        path = self.write('parse.vdf', '// comment\n"root" { "name" "A \\"quote\\"" "nested" { "size" "42" } }')
        self.assertEqual(storage.read_vdf(path)['root']['name'], 'A "quote"')
        path.write_text('"root" { "name" "}" }')
        self.assertEqual(storage.read_vdf(path)['root']['name'], '}')
        for bad in ['"a" {', '"a" "1" "a" "2"', '"a" }', 'garbage', '"a" {"b" "c"}}']:
            path.write_text(bad)
            with self.assertRaises(ValueError):
                storage.read_vdf(path)
        path.write_text('x' * (storage.MAX_TEXT + 1))
        with self.assertRaises(ValueError):
            storage.read_vdf(path)

    def test_http_probe_is_guarded_and_read_only(self):
        httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(server, 'ssh', return_value=json.dumps(self.inventory())) as ssh:
                conn = http.client.HTTPConnection(*httpd.server_address)
                conn.request('GET', '/api/storage')
                response = conn.getresponse()
                self.assertEqual(response.status, 403)
                response.read()
                ssh.assert_not_called()
                conn.request('GET', '/api/storage', headers={'X-Frame-UI': server.UI_KEY})
                response = conn.getresponse()
                self.assertEqual(response.status, 200)
                self.assertIn('libraries', json.loads(response.read()))
                self.assertEqual(ssh.call_args.args, ('python3 -',))
                self.assertEqual(ssh.call_args.kwargs['stdin'], (ROOT / 'ui/frame_storage.py').read_text())
                with patch.object(server, 'LINK', SimpleNamespace(active_device=lambda: {'id': 'new-frame'})):
                    ssh.reset_mock()
                    conn.request('GET', '/api/storage', headers={'X-Frame-UI': server.UI_KEY, 'X-Frame-Device': 'old-frame'})
                    response = conn.getresponse()
                    self.assertEqual(response.status, 409)
                    response.read()
                    ssh.assert_not_called()
                conn.close()
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join()

    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_ui_behavior(self):
        r = subprocess.run(['node', '--test', str(ROOT / 'tests/storage.cjs')], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
