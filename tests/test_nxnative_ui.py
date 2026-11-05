"""NxNative UI, route and shipping contracts without headset or ROM content."""
import sandbox  # noqa: F401
import fnmatch
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
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
                    'frame/nxnative/android-frame.patch', 'frame/nxnative/README.md', 'frame/nxnative/LICENSE.nxnative']
        for name in required:
            with self.subTest(name=name):
                self.assertIn(ROOT / name, phone)
                self.assertTrue(any(Path(name).is_relative_to(entry['from'].removeprefix('../')) and
                    any(fnmatch.fnmatch(str(Path(name).relative_to(entry['from'].removeprefix('../'))), pattern)
                        for pattern in entry.get('filter', ['**/*'])) for entry in resources))
        self.assertIn('frame/nxnative', frame_headset.ARCHIVE_DIRS)
        self.assertIn("'frame/nxnative/'", frame_headset.APPLY)

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
