"""The author ZIP checker uses the actual installer validator without installing."""
import sandbox  # noqa: F401
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'ui'))
import framey_panel

CHECKER = ROOT / 'scripts/framey-check-archive.py'
SAMPLE = ROOT / 'examples/framey-settings'


class ArchiveChecker(unittest.TestCase):
    def test_file_used_as_a_directory_is_rejected_without_installation(self):
        code, result = self.run_check(extra=('framey-settings/dist', 'not a directory'))
        self.assertEqual(code, 1, result)
        self.assertFalse(result['ok'])
        self.assertIn('file/directory collision', result['error'])

    def run_check(self, manifest=None, extra=None, frontend=True, bundle=None,
                  name='Framey Settings Sample', damage=None, members=(), expected_runtime=None,
                  manifest_bytes=None):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'plugin.zip'
            with zipfile.ZipFile(archive, 'w') as output:
                output.writestr('framey-settings/plugin.json',
                                manifest_bytes if manifest_bytes is not None else
                                json.dumps(manifest or json.loads((SAMPLE / 'plugin.json').read_text())))
                if frontend:
                    if bundle is None:
                        output.write(SAMPLE / 'dist/index.js', 'framey-settings/dist/index.js')
                    else:
                        output.writestr('framey-settings/dist/index.js', bundle)
                if extra:
                    output.writestr(extra[0], extra[1])
                for path, data in members:
                    output.writestr(path, data)
            if damage is not None:
                with zipfile.ZipFile(archive) as output:
                    entry = output.getinfo(damage)
                data = bytearray(archive.read_bytes())
                offset = entry.header_offset
                start = (offset + 30 + int.from_bytes(data[offset+26:offset+28], 'little')
                         + int.from_bytes(data[offset+28:offset+30], 'little'))
                data[start + entry.file_size - 1] ^= 1
                archive.write_bytes(data)
            run = subprocess.run([sys.executable, str(CHECKER), str(archive), '--name', name],
                                 capture_output=True, text=True, timeout=15)
            if expected_runtime is not None:
                plugins = Path(folder)/'plugins'
                with zipfile.ZipFile(archive) as output:
                    output.extractall(plugins)
                (plugins/'framey-settings/.frame-control-store.json').write_text(
                    json.dumps({'storeId':42, 'sha256':'a' * 64}))
                with patch.object(framey_panel, 'PLUGINS', plugins):
                    try:
                        framey_panel.local_bundle(42)
                        admitted = True
                    except FileNotFoundError:
                        admitted = False
                self.assertIs(admitted, expected_runtime, 'disposable runtime admission changed')
            return run.returncode, json.loads(run.stdout)

    def test_sample_has_an_accepted_panel_candidate(self):
        code, result = self.run_check()
        self.assertEqual(code, 0, result)
        self.assertTrue(result['installerAccepted'])
        self.assertTrue(result['panelCandidate'])
        self.assertEqual(result['folder'], 'framey-settings')
        self.assertEqual(len(result['sha256']), 64)
        self.assertIn('runtime tests', result['note'])

    def test_manifest_encoding_matches_installed_panel_admission(self):
        manifest = {'name': 'Exämple 日本語', 'api_version': 2, 'flags': []}
        text = json.dumps(manifest, ensure_ascii=False)
        for encoding in ('utf-16', 'utf-16-le', 'utf-16-be', 'utf-32',
                         'utf-32-le', 'utf-32-be', 'utf-8-sig'):
            with self.subTest(encoding=encoding):
                code, result = self.run_check(manifest_bytes=text.encode(encoding),
                                              name=manifest['name'], expected_runtime=False)
                self.assertEqual(code, 1, result)
                self.assertFalse(result['ok'])
                self.assertIn('manifest must be UTF-8', result['error'])
        code, result = self.run_check(manifest_bytes=text.encode('utf-8'),
                                      name=manifest['name'], expected_runtime=True)
        self.assertEqual(code, 0, result)
        self.assertTrue(result['panelCandidate'])

    def test_backend_only_archive_is_not_a_panel_candidate(self):
        code, result = self.run_check(frontend=False, extra=('framey-settings/README.txt', 'x' * 2048))
        self.assertEqual(code, 0, result)
        self.assertTrue(result['installerAccepted'])
        self.assertFalse(result['panelCandidate'])

    def test_empty_frontend_matches_installed_panel_admission(self):
        code, result = self.run_check(bundle=b'',
                                      extra=('framey-settings/README.txt', 'x' * 2048),
                                      expected_runtime=False)
        self.assertEqual(code, 0, result)
        self.assertTrue(result['installerAccepted'])
        self.assertFalse(result['panelCandidate'])

    def test_damaged_large_asset_fails_local_author_check(self):
        name = 'framey-settings/assets/large.bin'
        code, result = self.run_check(extra=(name, b'x' * 150_000), damage=name)
        self.assertEqual(code, 1, result)
        self.assertFalse(result['ok'])
        self.assertIn('CRC', result['error'])


    def test_large_manifest_passes_installer_but_not_panel_admission(self):
        manifest = json.loads((SAMPLE / 'plugin.json').read_text())
        manifest['description'] = 'x' * 17_000
        code, result = self.run_check(manifest=manifest)
        self.assertEqual(code, 0, result)
        self.assertTrue(result['installerAccepted'])
        self.assertFalse(result['panelCandidate'])

    def test_api_v1_requires_legacy_iife_or_decky_initializer(self):
        manifest = json.loads((SAMPLE / 'plugin.json').read_text())
        manifest['api_version'] = 1
        bundle = b'export default () => ({content: null});' + b' ' * 2000
        marker = b'__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit'
        cases = [
            (bundle, None, False),
            (bundle + marker, None, True),
            (bundle + b'./chunks/entry.js', ('framey-settings/dist/chunks/entry.js', marker), True),
        ]
        for frontend, extra, candidate in cases:
            with self.subTest(candidate=candidate, chunk=extra is not None):
                code, result = self.run_check(manifest=manifest, bundle=frontend, extra=extra)
                self.assertEqual(code, 0, result)
                self.assertEqual(result['panelCandidate'], candidate)

    def test_api_v1_chunk_candidates_match_runtime_file_and_directory_rules(self):
        manifest = json.loads((SAMPLE/'plugin.json').read_text())
        manifest['api_version'] = 1
        bundle = b"import './chunks/entry.js'; export default () => ({});" + b' ' * 2000
        marker = b'__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit'
        bridge = ('framey-settings/dist/chunks/entry.js', marker)
        cases = [
            ('regular bridge', (bridge,), True),
            ('explicit JS directory', (bridge, ('framey-settings/dist/chunks/unused.js/', '')), False),
            ('implicit JS directory', (bridge, ('framey-settings/dist/chunks/unused.js/data.json', '{}')), False),
            ('ordinary directory', (bridge, ('framey-settings/dist/chunks/assets/', '')), True),
            ('extensionless dotfile', (('framey-settings/dist/chunks/.js', marker),), False),
            ('dotfile with JS suffix', (('framey-settings/dist/chunks/.bridge.js', marker),), True),
        ]
        for label, members, accepted in cases:
            with self.subTest(layout=label):
                code, result = self.run_check(manifest=manifest, bundle=bundle, members=members,
                                              expected_runtime=accepted)
                self.assertEqual(code, 0, result)
                self.assertTrue(result['installerAccepted'])
                self.assertIs(result['panelCandidate'], accepted, label)

    def test_root_x86_and_wrong_store_name_are_rejected(self):
        cases = [
            ({'name': 'Framey Settings Sample', 'api_version': 2, 'flags': ['root']}, None,
             'Framey Settings Sample', 'needs root'),
            (None, ('framey-settings/bin/helper', b'\x7fELF' + b'\0' * 14 + b'\x3e\0' + b'\0' * 32),
             'Framey Settings Sample', 'non-ARM64'),
            (None, None, 'Different Store Name', 'name differs'),
        ]
        for manifest, extra, name, message in cases:
            with self.subTest(message=message):
                code, result = self.run_check(manifest=manifest, extra=extra, name=name)
                self.assertEqual(code, 1)
                self.assertFalse(result['ok'])
                self.assertIn(message, result['error'])


if __name__ == '__main__':
    unittest.main()
