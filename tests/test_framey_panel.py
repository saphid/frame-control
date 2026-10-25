"""Framey hosts only store-owned API v2 frontends and scopes backend calls."""
import sandbox  # noqa: F401
import gzip
import http.client
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tarfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'ui'))
import framey_panel
import frame_headset
import server


class Panel(unittest.TestCase):
    def test_opaque_origin_plugin_cache_is_scoped_and_bounded(self):
        result = subprocess.run(['node', str(Path(__file__).parent/'page/framey_cache.mjs')],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_vr_store_browsing_and_search(self):
        result = subprocess.run(['node', str(Path(__file__).parent/'page/framey_store.mjs')],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_plugin_quick_actions_and_settings(self):
        result = subprocess.run(['node', str(Path(__file__).parent/'page/framey_actions.mjs')],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.plugins = Path(tmp.name)/'plugins'
        self.folder = self.plugins/'protondb-decky'
        (self.folder/'dist').mkdir(parents=True)
        (self.folder/'.frame-control-store.json').write_text(json.dumps({'storeId':14,'version':'1.3.4'}))
        (self.folder/'plugin.json').write_text(json.dumps({'name':'ProtonDB Badges','api_version':2,'flags':[]}))
        (self.folder/'dist/index.js').write_text("export default () => ({content: SP_REACT.createElement('p', null, 'OK')});")
        home = patch.object(framey_panel, 'PLUGINS', self.plugins)
        home.start()
        self.addCleanup(home.stop)

    def test_owned_api_v2_bundle_is_embedded_without_ui_key(self):
        page = framey_panel.panel(14).decode()
        self.assertIn('framey-bundle', page)
        self.assertIn('/framey-runtime/host.js', page)
        self.assertIn('framey-toasts', page)
        self.assertNotIn('X-Frame-UI', page)
        self.assertNotIn('SP_REACT.createElement', page)  # bundled code is base64, not executable HTML.
        with self.assertRaises(FileNotFoundError):
            framey_panel.panel(15)

    def test_legacy_root_symlink_and_unmanaged_are_refused(self):
        manifest = self.folder/'plugin.json'
        manifest.write_text(json.dumps({'name':'ProtonDB Badges','api_version':1}))
        with self.assertRaises(FileNotFoundError): framey_panel.panel(14)
        manifest.write_text(json.dumps({'name':'ProtonDB Badges','api_version':2,'flags':['root']}))
        with self.assertRaises(FileNotFoundError): framey_panel.panel(14)
        manifest.write_text(json.dumps({'name':'ProtonDB Badges','api_version':2,'flags':[]}))
        dist = self.folder/'dist'
        dist.rename(self.folder/'saved-dist')
        dist.symlink_to(self.folder/'saved-dist')
        with self.assertRaises(FileNotFoundError): framey_panel.panel(14)
        dist.unlink()
        (self.folder/'.frame-control-store.json').unlink()
        with self.assertRaises(FileNotFoundError): framey_panel.panel(14)

    def test_backend_method_is_scoped_to_store_receipt(self):
        def fake_ssh(command, stdin=None, **_):
            self.assertIn('python3 - ', command)
            self.assertEqual(stdin, framey_panel.METHOD_SCRIPT)
            return json.dumps({'result':{'theme':'dark'}})
        with patch.object(framey_panel.frame_decky, 'status', return_value={
            'plugins':[{'storeId':14,'name':'ProtonDB Badges'}]}):
            self.assertEqual(framey_panel.call_method(fake_ssh,14,'get_setting',['theme','dark']),
                             {'result':{'theme':'dark'}})
            with self.assertRaises(framey_panel.PanelError): framey_panel.call_method(fake_ssh,15,'get_setting',[])
            with self.assertRaises(framey_panel.PanelError): framey_panel.call_method(fake_ssh,14,'x;alert(1)',[])
        compile(framey_panel.METHOD_SCRIPT, '<remote method>', 'exec')

    def test_headset_bundle_contains_runtime_and_licenses(self):
        packed = frame_headset.bundle()
        self.assertGreater(len(packed), 100_000)
        self.assertLess(len(packed), frame_headset.MAX_ARCHIVE)
        with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as archive:
            names = set(archive.getnames())
        self.assertTrue({'ui/framey_panel.py','ui/framey-host.js',
                         'ui/vendor/react-18.3.1.min.js','ui/vendor/react-dom-18.3.1.min.js',
                         'ui/vendor/REACT-LICENSE.txt','ui/vendor/REACT-DOM-LICENSE.txt'} <= names)

    def test_http_panel_is_sandboxable_and_missing_plugin_is_404(self):
        httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        def get(path):
            conn = http.client.HTTPConnection('127.0.0.1', httpd.server_port, timeout=5)
            try:
                conn.request('GET', path)
                reply = conn.getresponse()
                return reply.status, dict(reply.getheaders()), reply.read()
            finally:
                conn.close()
        status, headers, body = get('/framey/panel/14')
        self.assertEqual(status, 200)
        self.assertIn('blob:', headers['Content-Security-Policy'])
        self.assertIn(b'framey-bundle', body)
        self.assertEqual(get('/framey/panel/15')[0], 404)


if __name__ == '__main__':
    unittest.main()
