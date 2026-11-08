"""Pinned Storage Cleaner transport repair preserves managed delete restrictions."""
import sandbox  # noqa: F401
import hashlib
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile

from framey_official import MANAGED_FRONTENDS, PLUGINS, archive
import test_frame_decky_store as transactions
import frame_decky_store
import framey_compatibility

ROOT = Path(__file__).resolve().parents[1]
PREFIX = (b'from framey_decky_ipc import install as _framey_install_ipc_eof\n'
          b'_framey_install_ipc_eof()\ndel _framey_install_ipc_eof\n')
PRIOR_BODY = '8e01ebd0f5304d3e27c10352a31510e168cdac377e0aabd3cc485c2328c1f14d'


@unittest.skipIf(os.name == 'nt', 'remote plugin transaction requires POSIX')
class StorageCleanerIpc(unittest.TestCase):
    def setUp(self):
        self.tx = transactions.StoreTransaction()
        self.tx.setUp()
        self.addCleanup(self.tx.doCleanups)
        self.pin = next(p for p in PLUGINS if p['id'] == 50)
        self.data = archive(self.pin)
        self.folder = self.tx.folder.parent/self.pin['folder']

    def install(self):
        return self.tx.apply('install', self.data, plugin_id=50,
                             folder=self.pin['folder'], version=self.pin['version'])

    def test_installed_ipc_preserves_prior_managed_body_and_other_archive_files(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        source = (self.folder/'main.py').read_bytes()
        self.assertTrue(source.startswith(PREFIX))
        self.assertEqual(hashlib.sha256(source[len(PREFIX):]).hexdigest(), PRIOR_BODY)
        self.assertEqual((self.folder/'py_modules/framey_decky_ipc.py').read_bytes(),
                         (ROOT/'ui/framey_decky_ipc.py').read_bytes())
        self.assertEqual(hashlib.sha256((self.folder/'dist/index.js').read_bytes()).hexdigest(),
                         MANAGED_FRONTENDS[50])
        with zipfile.ZipFile(io.BytesIO(self.data)) as bundle:
            for entry in bundle.infolist():
                relative = entry.filename.split('/', 1)[-1]
                if not entry.is_dir() and relative not in ('main.py', 'dist/index.js'):
                    self.assertEqual((self.folder/relative).read_bytes(), bundle.read(entry), relative)
        receipt = json.loads((self.folder/'.frame-control-store.json').read_text())
        self.assertEqual(receipt['compatShims'], ['storage-cleaner-bounded-delete', 'storage-cleaner-ipc-eof'])

    def test_missing_adapter_refuses_update_and_preserves_installed_copy(self):
        self.assertEqual(self.install().returncode, 0)
        before = {str(p.relative_to(self.folder)): p.read_bytes() for p in self.folder.rglob('*') if p.is_file()}
        script = frame_decky_store.apply_script(50, self.pin['sha256'])
        script = script.replace('FRAMEY_STORAGE_CLEANER_IPC_SOURCE = '+repr((ROOT/'ui/framey_decky_ipc.py').read_text()),
                                'FRAMEY_STORAGE_CLEANER_IPC_SOURCE = None')
        with patch.object(frame_decky_store, 'apply_script', return_value=script):
            result = self.tx.apply('update', self.data, expected=self.pin['sha256'], plugin_id=50,
                                   folder=self.pin['folder'], version=self.pin['version'])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Missing Storage Cleaner child IPC EOF repair', result.stderr)
        self.assertEqual(before, {str(p.relative_to(self.folder)): p.read_bytes()
                                 for p in self.folder.rglob('*') if p.is_file()})

    def test_modified_archive_does_not_inherit_ipc_repair(self):
        stream = io.BytesIO(self.data)
        with zipfile.ZipFile(stream, 'a') as bundle:
            original = bundle.read(self.pin['folder']+'/main.py')
            bundle.writestr(self.pin['folder']+'/changed.txt', b'Unrecognized release')
        data = stream.getvalue()
        digest = hashlib.sha256(data).hexdigest()
        self.assertEqual(frame_decky_store.apply_script(50, digest), frame_decky_store.APPLY)
        result = self.tx.apply('install', data, plugin_id=50, folder=self.pin['folder'], version=self.pin['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.folder/'main.py').read_bytes(), original)
        self.assertFalse((self.folder/'py_modules/framey_decky_ipc.py').exists())

    def test_old_receipt_requires_reinstall_without_claiming_full_plugin_support(self):
        old = framey_compatibility.lookup(50, self.pin['sha256'], self.pin['version'],
                                        installed_shims=['storage-cleaner-bounded-delete'])
        repaired = framey_compatibility.lookup(50, self.pin['sha256'], self.pin['version'],
                 installed_shims=['storage-cleaner-bounded-delete', 'storage-cleaner-ipc-eof'])
        self.assertIn('Update or reinstall', old['reason'])
        self.assertNotIn('Update or reinstall', repaired['reason'])
        self.assertEqual(repaired['status'], 'partial')
