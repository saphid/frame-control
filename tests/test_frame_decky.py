"""Decky release validation and the removable user-service transaction."""
import sandbox  # noqa: F401
import hashlib
import io
import json
import os
import secrets
import subprocess
import sys
import tempfile
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
        self.assertTrue((Path(self.tmp.name) / '.config/systemd/user/frame-control-decky.service').is_file())

        second = arm_binary(b'B')
        result = self.apply('update', second, version='v3.3.1', fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.base / 'PluginLoader').read_bytes(), first)
        self.assertEqual(json.loads(receipt.read_text())['version'], 'v3.3.0')

        result = self.apply('update', second, version='v3.3.1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.base / 'PluginLoader').read_bytes(), second)
        result = self.apply('remove')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.base / 'PluginLoader').exists())
        self.assertFalse(receipt.exists())
        self.assertTrue((self.base / 'plugins').is_dir())
