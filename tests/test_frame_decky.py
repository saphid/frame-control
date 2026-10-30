"""Decky release validation and the removable user-service transaction."""
import sandbox  # noqa: F401
import hashlib
import http.server
import io
import json
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'ui'))
import frame_decky


def arm_binary(fill=b'A'):
    data = bytearray(b'\x7fELF' + fill * 2044)
    data[18:20] = (183).to_bytes(2, 'little')
    return bytes(data)


class DeckyRelease(unittest.TestCase):
    def test_official_arm_release_digest_is_checked(self):
        data = arm_binary()
        digest = hashlib.sha256(data).hexdigest()
        url = f'https://github.com/{frame_decky.REPO}/releases/download/v3.3.0/PluginLoader-arm64'
        info = {'tag_name':'v3.3.0', 'assets':[{'name':'PluginLoader-arm64', 'size':len(data),
                'digest':'sha256:'+digest, 'browser_download_url':url}]}
        with patch.object(frame_decky.urllib.request, 'urlopen', side_effect=[io.BytesIO(json.dumps(info).encode()), io.BytesIO(data)]):
            self.assertEqual(frame_decky.release_binary(), ('v3.3.0', digest, data))
        info['assets'][0]['digest'] = 'sha256:' + '0'*64
        with patch.object(frame_decky.urllib.request, 'urlopen', side_effect=[io.BytesIO(json.dumps(info).encode()), io.BytesIO(data)]):
            with self.assertRaisesRegex(ValueError, 'digest'):
                frame_decky.release_binary()

    def test_install_rejects_incompatible_headset_before_download(self):
        state = {'arch':'x86_64','variant':'vr','cef':True,'managed':False,'upstreamInstall':False}
        with patch.object(frame_decky, 'release_binary') as download:
            with self.assertRaisesRegex(ValueError, 'Steam Frame'):
                frame_decky.change(lambda *a, **k: json.dumps(state), 'install')
            download.assert_not_called()


@unittest.skipIf(os.name == 'nt', 'remote status script runs on Linux')
class DeckyStatusProbe(unittest.TestCase):
    def test_panel_status_reads_fresh_ownership_and_inventory_without_network_imports(self):
        guard = '''import builtins
original_import = builtins.__import__
def panel_import(name, *args, **kwargs):
    if name in ('http.client', 'urllib.request', 'platform'):
        raise AssertionError('unrelated panel status import: '+name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = panel_import
'''
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            base = home / '.local/share/frame-control/decky'
            plugin = base / 'plugins/Example/plugin.json'
            plugin.parent.mkdir(parents=True)
            plugin.write_text(json.dumps({'name': 'Example', 'author': 'Test'}))
            marker = plugin.with_name('.frame-control-store.json')
            marker.write_text(json.dumps({'storeId': 14, 'version': '1.0', 'sha256': 'a'*64}))
            receipt = base / '.frame-control/receipt.json'
            receipt.parent.mkdir()
            legacy = base / 'settings/release.json'
            legacy.parent.mkdir()
            service = home / '.config/systemd/user/frame-control-decky.service'
            service.parent.mkdir(parents=True)
            service.write_text('owned service canary\n')
            systemctl = home / 'systemctl'
            systemctl.write_text('#!/bin/sh\n[ "$1 $2 $3" = "--user is-active frame-control-decky.service" ] || exit 99\nexit "$PANEL_TEST_STATE"\n')
            systemctl.chmod(0o700)
            def probe(active=True):
                before = {p: p.read_bytes() for p in home.rglob('*') if p.is_file()}
                result = subprocess.run([sys.executable, '-'], input=guard+frame_decky.PANEL_STATUS_PROBE,
                    capture_output=True, text=True, timeout=15,
                    env={**os.environ, 'HOME': folder, 'PANEL_TEST_STATE': '0' if active else '3',
                         'PATH': folder+os.pathsep+os.environ['PATH']})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual({p: p.read_bytes() for p in home.rglob('*') if p.is_file()}, before)
                state = json.loads(result.stdout)
                self.assertEqual(set(state), {'managed', 'running', 'version', 'plugins'})
                self.assertIs(state['running'], active)
                return state
            owned = {'managedBy': 'Frame Control', 'version': 'v3.3.0'}
            receipt.write_text(json.dumps(owned))
            state = probe()
            self.assertTrue(state['managed'])
            self.assertEqual(state['version'], 'v3.3.0')
            self.assertEqual(state['plugins'][0]['sha256'], 'a'*64)
            # Each refresh must see the current installed receipt, even when stopped.
            marker.write_text(json.dumps({'storeId': 14, 'version': '2.0', 'sha256': 'b'*64}))
            state = probe(False)
            self.assertTrue(state['managed'])
            self.assertEqual(state['plugins'][0]['sha256'], 'b'*64)
            receipt.unlink()
            legacy.write_text(json.dumps(owned))
            self.assertTrue(probe()['managed'])
            receipt.write_text(json.dumps({'managedBy': 'someone else', 'version': 'v9.0.0'}))
            self.assertFalse(probe()['managed'])  # New receipt takes precedence over legacy.
            self.assertIsNone(probe()['version'])
            receipt.unlink()
            legacy.unlink()
            self.assertFalse(probe()['managed'])
            receipt.write_text(json.dumps(owned))
            service.unlink()
            self.assertFalse(probe()['managed'])

    def test_panel_status_preserves_transport_deadline_and_compatibility(self):
        plugin = {'storeId': 14, 'version': '1.0', 'sha256': 'a'*64}
        def ssh(command, stdin, timeout):
            self.assertEqual((command, stdin, timeout), ('python3 -', frame_decky.PANEL_STATUS_PROBE, 15))
            return json.dumps({'managed': True, 'running': True, 'version': 'v3.3.0', 'plugins': [plugin]})
        result = frame_decky.panel_status(ssh)
        self.assertIn('compatibility', result['plugins'][0])
        self.assertEqual(result['plugins'][0]['sha256'], plugin['sha256'])

    def test_loopback_status_preserves_inventory_when_cef_is_unavailable(self):
        replies = []
        requests = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                code, body = replies.pop(0)
                self.send_response(code)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            base = home / '.local/share/frame-control/decky'
            plugin = base / 'plugins/Example/plugin.json'
            plugin.parent.mkdir(parents=True)
            plugin.write_text(json.dumps({'name': 'Example', 'author': 'Test'}))
            receipt = base / '.frame-control/receipt.json'
            receipt.parent.mkdir()
            receipt.write_text(json.dumps({'managedBy': 'Frame Control', 'version': 'v3.3.0'}))
            service = home / '.config/systemd/user/frame-control-decky.service'
            service.parent.mkdir(parents=True)
            service.write_text('owned service canary\n')
            systemctl = home / 'systemctl'
            systemctl.write_text('#!/bin/sh\nexit 0\n')
            systemctl.chmod(0o700)
            before = {p: p.read_bytes() for p in (plugin, receipt, service)}
            server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                probe = frame_decky.PROBE.replace('8080, timeout=2', str(server.server_port)+', timeout=2')
                # The cold remote probe must not load URL/proxy/TLS helpers.
                guard = '''import builtins
original_import = builtins.__import__
def bounded_import(name, *args, **kwargs):
    if name in ('urllib.request', 'platform'):
        raise AssertionError('cold status import: '+name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = bounded_import
'''
                targets = json.dumps([{'title': 'SharedJSContext',
                                       'url': 'http://steamloopback.host/index.html'}]).encode()
                for code, body, expected in ((200, targets, True), (200, b'[]', False),
                                             (503, targets, False), (200, b'invalid json', False)):
                    with self.subTest(code=code, body=body):
                        replies.append((code, body))
                        result = subprocess.run([sys.executable, '-'], input=guard+probe,
                            capture_output=True, text=True, timeout=15,
                            env={**os.environ, 'HOME': folder,
                                 'PATH': folder+os.pathsep+os.environ['PATH']})
                        self.assertEqual(result.returncode, 0, result.stderr)
                        status = json.loads(result.stdout)
                        self.assertIs(status['cef'], expected)
                        self.assertIs(status['managed'], True)
                        self.assertIs(status['running'], True)
                        self.assertEqual(status['arch'], os.uname().machine)
                        self.assertEqual(status['version'], 'v3.3.0')
                        self.assertEqual(status['plugins'][0]['name'], 'Example')
                        self.assertEqual({p: p.read_bytes() for p in before}, before)
                self.assertEqual(requests, ['/json/list']*4)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
                self.assertFalse(thread.is_alive())


@unittest.skipIf(os.name == 'nt', 'remote service script runs on Linux')
class DeckyServiceScript(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        home = Path(self.tmp.name)
        fake = home / 'systemctl'
        fake.write_text('#!/bin/sh\nif [ "$FRAME_DECKY_TEST_FAIL" = "1" ] && [ "$2" = "enable" ]; then echo blocked >&2; exit 1; fi\nexit 0\n')
        fake.chmod(0o700)
        self.env = {**os.environ, 'HOME': self.tmp.name, 'PATH': self.tmp.name + os.pathsep + os.environ['PATH']}
        self.base = home / '.local/share/frame-control/decky'

    def apply(self, action, data=None, version='v3.3.0', fail=False):
        token = secrets.token_hex(12)
        stage = Path('/tmp/frame-control-decky-' + token)
        if data is not None:
            stage.write_bytes(data)
        digest = hashlib.sha256(data or b'').hexdigest()
        env = {**self.env, 'FRAME_DECKY_TEST_FAIL': '1' if fail else '0'}
        try:
            return subprocess.run([sys.executable, '-', action, token, digest, version],
                                  input=frame_decky.APPLY, capture_output=True, text=True, env=env, timeout=15)
        finally:
            stage.unlink(missing_ok=True)

    def test_install_update_rollback_and_remove(self):
        first = arm_binary(b'A')
        result = self.apply('install', first)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.base / 'PluginLoader').read_bytes(), first)
        receipt = self.base / '.frame-control/receipt.json'
        self.assertEqual(json.loads(receipt.read_text())['version'], 'v3.3.0')
        service = Path(self.tmp.name) / '.config/systemd/user/frame-control-decky.service'
        first_unit = service.read_text()
        self.assertIn('\nKillMode=mixed\n', first_unit)
        self.assertIn('Environment=PATH='+str(Path(self.tmp.name) / '.local/bin')+
                      ':/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n', first_unit)

        second = arm_binary(b'B')
        result = self.apply('update', second, version='v3.3.1', fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.base / 'PluginLoader').read_bytes(), first)
        self.assertEqual(json.loads(receipt.read_text())['version'], 'v3.3.0')
        self.assertEqual(service.read_text(), first_unit)

        result = self.apply('update', second, version='v3.3.1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.base / 'PluginLoader').read_bytes(), second)
        self.assertIn('Environment=PATH=', service.read_text())
        self.assertIn('\nKillMode=mixed\n', service.read_text())
        result = self.apply('remove')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.base / 'PluginLoader').exists())
        self.assertFalse(receipt.exists())
        self.assertTrue((self.base / 'plugins').is_dir())
