"""NxNative UI, route and shipping contracts without headset or ROM content."""
import sandbox  # noqa: F401
import fnmatch
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ui'))


class NxNativeUI(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node exercises production controller')
    def test_controller(self):
        result = subprocess.run(['node', '--test', str(ROOT / 'tests/nxnative_ui.cjs')],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_helpers_ship_in_desktop_phone_and_headset(self):
        import frame_headset
        spec = importlib.util.spec_from_file_location('nxnative_phone_bundle', ROOT / 'ios/scripts/make_frame_bundle.py')
        bundle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bundle)
        phone = set(bundle.files())
        resources = json.loads((ROOT / 'app/package.json').read_text())['build']['extraResources']
        required = ['ui/frame_nxnative.py', 'ui/nxnative.js', 'frame/nxnative/stage.py',
                    'frame/nxnative/build.py', 'frame/nxnative/extract_romfs.py',
                    'frame/nxnative/android-frame.patch', 'frame/nxnative/README.md', 'frame/nxnative/LICENSE.nxnative',
                    'frame/nxnative/profiles/01002B30028F6000/game.tsv',
                    'frame/nxnative/profiles/01002B30028F6000/dmsh_chain.h',
                    'frame/love/package.py', 'frame/love/README.md', 'frame/love/clipboard.py',
                    'frame/love/SDLClipboardHandler.java', 'frame/love/LICENSE.SDL.txt']
        required += [p.relative_to(ROOT).as_posix() for p in
                     (ROOT / 'frame/nxnative/profiles').rglob('*') if p.is_file()]
        for name in required:
            with self.subTest(name=name):
                self.assertIn(ROOT / name, phone)
                self.assertTrue(any(Path(name).is_relative_to(entry['from'].removeprefix('../')) and
                    any(fnmatch.fnmatch(str(Path(name).relative_to(entry['from'].removeprefix('../'))), pattern)
                        for pattern in entry.get('filter', ['**/*'])) for entry in resources))
        self.assertIn('frame/nxnative', frame_headset.ARCHIVE_DIRS)
        self.assertIn("'frame/nxnative/'", frame_headset.APPLY)

    @unittest.skipUnless(shutil.which('node'), 'Node exercises desktop resource gate')
    def test_desktop_gate_requires_complete_shader_profile(self):
        result = subprocess.run(['node', '-e',
            'process.stdout.write(JSON.stringify(require(process.argv[1]).REQUIRED))',
            str(ROOT / 'app/build/check-resources.js')], capture_output=True, text=True, check=True)
        required = set(json.loads(result.stdout))
        for path in (ROOT / 'frame/nxnative/profiles').rglob('*'):
            if path.suffix in ('.tsv', '.h'):
                self.assertIn(path.relative_to(ROOT).as_posix(), required)

    def test_phone_bundle_excludes_game_outputs_and_private_sources(self):
        spec = importlib.util.spec_from_file_location('nxnative_phone_boundary', ROOT / 'ios/scripts/make_frame_bundle.py')
        bundle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bundle)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            public = {'frame/nxnative/build.py', 'frame/love/package.py',
                      'frame/nxnative/profiles/title/game.tsv'}
            private = {'frame/nxnative/game.apk', 'frame/nxnative/game.nxnative.zip',
                       'frame/nxnative/catalog.json', 'frame/nxnative/prod.keys',
                       'frame/nxnative/build/frame-inputs.json',
                       'frame/nxnative/build/module.so', 'frame/love/game.apk',
                       'frame/love/game/main.lua', 'frame/love/assets/game.love'}
            for name in public | private:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('sentinel')
            with mock.patch.object(bundle, 'ROOT', root):
                self.assertEqual({p.relative_to(root).as_posix() for p in bundle.files()}, public)

    def test_route_validation_precedes_network_and_install_uses_queue(self):
        import server
        for body in ({}, {'action':'add','location':False}, {'action':'remove','source':''},
                     {'action':'install','source':'s','id':'\0bad'}):
            with self.subTest(body=body), mock.patch.object(server, 'ensure_master') as network:
                with self.assertRaises(server.Failure):
                    server.nxnative_action(body)
                network.assert_not_called()
        with mock.patch.object(server, 'ensure_master'), \
             mock.patch.object(server, 'queue_job', return_value={'job':'queued'}) as queue, \
             mock.patch.object(server.frame_nxnative, 'install', return_value={'message':'installed'}) as install:
            self.assertEqual(server.nxnative_action({'action':'install','source':'s','id':'g'}), {'job':'queued'})
            install.assert_not_called()
            callback = queue.call_args.args[1]
            progress = mock.Mock()
            self.assertEqual(callback(progress), {'message':'installed'})
            install.assert_called_once_with('s', 'g', report=progress)
            self.assertTrue(queue.call_args.kwargs['progress'])


if __name__ == '__main__':
    unittest.main()
