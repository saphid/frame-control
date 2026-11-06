"""Headset panel packaging, ownership checks and window targeting."""
import sandbox  # noqa: F401
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ui'))
import frame_headset
import frame_headset_runtime


class HeadsetBundle(unittest.TestCase):
    def test_bundle_is_deterministic_and_contains_the_local_ui(self):
        first = frame_headset.bundle()
        self.assertEqual(first, frame_headset.bundle())
        with tarfile.open(fileobj=io.BytesIO(first), mode='r:gz') as archive:
            names = set(archive.getnames())
        self.assertIn('ui/headset.html', names)
        self.assertIn('ui/frame_headset_runtime.py', names)
        self.assertIn('ui/server.py', names)
        for name in ('stage.py', 'build.py', 'extract_romfs.py', 'android-frame.patch', 'LICENSE.nxnative'):
            self.assertIn('frame/nxnative/' + name, names)
        self.assertIn('ui/frame_nxnative.py', names)
        self.assertIn('ui/nxnative.js', names)
        for path in (frame_headset.ROOT / 'frame/nxnative/profiles').rglob('*'):
            if path.is_file():
                self.assertIn(path.relative_to(frame_headset.ROOT).as_posix(), names)
        self.assertIn('frame/love/package.py', names)
        self.assertIn('frame/love/README.md', names)
        self.assertIn('frame/love/clipboard.py', names)
        self.assertIn('frame/love/SDLClipboardHandler.java', names)
        self.assertIn('frame/love/LICENSE.SDL.txt', names)
        for filename in ('aarch64.gz', 'x86_64.gz', 'source.tar.gz', 'LICENSE.txt', 'GO-LICENSE.txt', 'README.md'):
            self.assertIn('ui/vendor/deckyfileserver-1.2.0/'+filename, names)
        for filename in ('aarch64.gz', 'source.tar.gz', 'LICENSE.txt', 'GO-LICENSE.txt', 'README.md'):
            self.assertIn('ui/vendor/localsend-0.4.5/'+filename, names)
        self.assertIn('scripts/build-framey-fileserver.py', names)
        for name in ('aarch64.whl', 'x86_64.whl', 'LICENSE.txt'):
            self.assertIn('ui/vendor/psutil-7.2.2/'+name, names)
        self.assertFalse(any('\\' in name for name in names))
        self.assertFalse(any('__pycache__' in name for name in names))

    def test_game_builds_private_sources_and_keys_are_not_shipped(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            public = ['frame/nxnative/build.py', 'frame/nxnative/android-frame.patch',
                      'frame/nxnative/LICENSE.nxnative',
                      'frame/nxnative/profiles/01002B30028F6000/game.tsv',
                      'frame/nxnative/profiles/01002B30028F6000/dmsh_chain.h',
                      'frame/love/package.py', 'frame/love/README.md']
            private = ['frame/nxnative/game.apk', 'frame/nxnative/game.nxnative.zip',
                       'frame/nxnative/prod.keys', 'frame/nxnative/catalog.json',
                       'frame/nxnative/build/frame-inputs.json',
                       'frame/nxnative/build/modules.txt',
                       'frame/nxnative/build/romfs/main.lua',
                       'frame/nxnative/build/libdmhost.so',
                       'frame/nxnative/build/shader/vk/effect.spv',
                       'frame/love/game.apk', 'frame/love/catalog.json',
                       'frame/love/assets/game.love', 'frame/love/game/main.lua']
            for name in public + private:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('sentinel')
            with patch.object(frame_headset, 'ROOT', root):
                packed = frame_headset.bundle()
            with tarfile.open(fileobj=io.BytesIO(packed), mode='r:gz') as archive:
                self.assertEqual(set(archive.getnames()), set(public))

    def test_incompatible_device_is_rejected_before_upload(self):
        state = {'arch': 'x86_64', 'variant': 'vr'}
        calls = []
        def ssh(*args, **kwargs):
            calls.append(args)
            return json.dumps(state)
        with patch.object(frame_headset, 'bundle') as bundle:
            with self.assertRaisesRegex(ValueError, 'Steam Frame'):
                frame_headset.change(ssh, 'install')
            bundle.assert_not_called()
        self.assertEqual(len(calls), 1)

    @unittest.skipIf(os.name == 'nt', 'remote script runs on Linux')
    def test_unowned_install_is_never_removed(self):
        with tempfile.TemporaryDirectory() as home:
            token = secrets.token_hex(12)
            result = subprocess.run([sys.executable, '-', 'remove', token, 'none'],
                                    input=frame_headset.APPLY, text=True, capture_output=True,
                                    env={**os.environ, 'HOME': home}, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('No Frame Control managed', result.stderr)


class HeadsetWindow(unittest.TestCase):
    def test_uses_only_its_marker_title(self):
        tree = ' 0x101 "Other panel"\n 0xabc "Frame Control VR [fc-headset]"\n'
        with patch.object(frame_headset_runtime, 'command', return_value=tree):
            self.assertEqual(frame_headset_runtime.panel_window(), '0xabc')
        with patch.object(frame_headset_runtime, 'command', return_value=' 0x101 "Other panel"'):
            self.assertIsNone(frame_headset_runtime.panel_window())


if __name__ == '__main__':
    unittest.main()
