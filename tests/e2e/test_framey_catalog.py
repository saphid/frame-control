"""Optional full-catalog archive/transport audit; no official backend executes."""
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from harness import FrameTestCase, ROOT, Server, finished, ok, require, ssh
import frame_decky_store
from framey_official import MANAGED_FRONTENDS

require()


@unittest.skipUnless(os.environ.get('FRAMEY_AUDIT_CACHE'), 'optional full catalog audit cache not mounted')
class CatalogAudit(FrameTestCase):
    def backend(self):
        # Only the fake service/CEF stub executes. Official Python/native code
        # copied by the installer is never imported or launched by this harness.
        source = '''import json,pathlib
h=pathlib.Path.home();b=h/'.local/share/frame-control/decky/.frame-control';b.mkdir(parents=True,exist_ok=True)
(b/'receipt.json').write_text(json.dumps({'managedBy':'Frame Control','version':'v3.3.0'}))
(b.parent/'plugins').mkdir(exist_ok=True)
u=h/'.config/systemd/user/frame-control-decky.service';u.parent.mkdir(parents=True,exist_ok=True);u.write_text('[Service]')'''
        ssh('python3 -c '+shlex.quote(source))
        ssh('mkdir -p ~/.local/share/frame-control/headset/bundle/ui')
        result = subprocess.run(['ssh', 'frame', 'cat > ~/.local/share/frame-control/headset/bundle/ui/frame_steam.py'],
                                input=(ROOT/'ui/frame_steam.py').read_bytes(), capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    @classmethod
    def setUpClass(cls):
        records = json.loads((ROOT/'ui/framey-compatibility.json').read_text())['plugins']
        cache = Path(os.environ['FRAMEY_AUDIT_CACHE'])

        class Fixture(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                if self.path == '/plugins':
                    body = json.dumps([{'id': p['id'], 'name': p['name'], 'tags': p['tags'],
                                        'versions': [{'name': p['version'], 'hash': p['sha256']}]}
                                       for p in records]).encode()
                else:
                    path = cache / self.path.rsplit('/', 1)[-1]
                    if path.suffix != '.zip' or path.name not in {p['sha256']+'.zip' for p in records}:
                        self.send_error(404)
                        return
                    body = path.read_bytes()
                self.send_response(200)
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # Installer stops reading at its archive size limit.

        fixture = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
        cls.addClassCleanup(fixture.server_close)
        cls.addClassCleanup(fixture.shutdown)
        threading.Thread(target=fixture.serve_forever, daemon=True).start()
        old = {k: os.environ.get(k) for k in ('FRAMEY_STORE_URL', 'FRAMEY_CDN_URL')}
        def restore():
            Server.stop()
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        cls.addClassCleanup(restore)
        os.environ['FRAMEY_STORE_URL'] = f'http://127.0.0.1:{fixture.server_port}/plugins'
        os.environ['FRAMEY_CDN_URL'] = f'http://127.0.0.1:{fixture.server_port}/versions/'
        Server.stop()
        super().setUpClass()

    def test_all_current_official_archives(self):
        self.backend()
        records = json.loads((ROOT/'ui/framey-compatibility.json').read_text())['plugins']
        cache = Path(os.environ['FRAMEY_AUDIT_CACHE'])
        catalog = {p['id']: p for p in ok('GET', '/api/decky/store')['plugins']}
        self.assertEqual(set(catalog), {p['id'] for p in records})
        results = []
        for plugin in records:
            with self.subTest(plugin=plugin['name']):
                data = (cache/(plugin['sha256']+'.zip')).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), plugin['sha256'])
                validation = None
                try:
                    folder = frame_decky_store.archive_info(data, plugin['sha256'], plugin['name'])
                except ValueError as error:
                    validation = str(error)
                blocked = catalog[plugin['id']]['root'] or plugin['blockInstall'] or validation
                job = finished(ok('POST', '/api/decky/plugin', {'action': 'install', 'id': plugin['id'],
                    'sha256': plugin['sha256'], 'acknowledged': True}))
                record = {'id': plugin['id'], 'sha256': plugin['sha256'],
                          'archiveValidation': validation or 'accepted', 'result': 'blocked' if blocked else 'installed-removed'}
                if blocked:
                    self.assertTrue(job.get('error'), job)
                    record['reason'] = job['error']
                    self.assertFalse(any(p['storeId'] == plugin['id'] for p in ok('GET', '/api/decky')['plugins']))
                else:
                    self.assertFalse(job.get('error'), job)
                    installed = f'~/.local/share/frame-control/decky/plugins/{folder}'
                    with zipfile.ZipFile(io.BytesIO(data)) as archive:
                        entry = folder+'/dist/index.js'
                        if entry in archive.namelist():
                            expected = MANAGED_FRONTENDS.get(plugin['id'], hashlib.sha256(archive.read(entry)).hexdigest())
                            self.assertEqual(ssh(f'sha256sum {installed}/dist/index.js').split()[0], expected)
                    found = next(p for p in ok('GET', '/api/decky')['plugins'] if p['storeId'] == plugin['id'])
                    self.assertEqual((found['version'], found['sha256']), (plugin['version'], plugin['sha256']))
                    removed = finished(ok('POST', '/api/decky/plugin', {'action': 'remove', 'id': plugin['id'], 'acknowledged': True}))
                    self.assertFalse(removed.get('error'), removed)
                    self.assertFalse(any(p['storeId'] == plugin['id'] for p in ok('GET', '/api/decky')['plugins']))
                results.append(record)
                Path(os.environ.get('FRAMEY_AUDIT_OUTPUT', '/tmp/framey-catalog-result.json')).write_text(json.dumps(results, indent=2)+'\n')
