"""The exact installed ProtonDB archive keeps its published settings and frontend."""
import sandbox  # noqa: F401
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import unittest
import zipfile

import framey_official
import test_frame_decky_store as transactions
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'ui'))
import frame_decky_store

ROOT = Path(__file__).resolve().parents[1]
PREFIX = (b'from framey_decky_ipc import install as _framey_install_ipc_eof\n'
          b'_framey_install_ipc_eof()\ndel _framey_install_ipc_eof\n')


@unittest.skipIf(os.name == 'nt', 'managed remote transaction requires POSIX')
class ProtondbLifecycle(unittest.TestCase):
    def test_exact_archive_preserves_every_published_member_and_adds_only_child_repair(self):
        tx = transactions.StoreTransaction()
        tx.setUp()
        self.addCleanup(tx.doCleanups)
        pin = next(p for p in framey_official.PLUGINS if p['id'] == 14)
        raw = framey_official.archive(pin)
        result = tx.apply('install', raw, plugin_id=14, folder=pin['folder'], version=pin['version'])
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = tx.folder.parent / pin['folder']
        with zipfile.ZipFile(io.BytesIO(raw)) as packed:
            for member in packed.infolist():
                if member.is_dir():
                    continue
                name = member.filename.split('/', 1)[1]
                expected = packed.read(member)
                self.assertEqual((folder/name).read_bytes(), PREFIX+expected if name == 'main.py' else expected)
        self.assertEqual((folder/'py_modules/framey_decky_ipc.py').read_bytes(),
                         (ROOT/'ui/framey_decky_ipc.py').read_bytes())
        receipt = json.loads((folder/'.frame-control-store.json').read_text())
        self.assertEqual(receipt['compatShims'], ['protondb-ipc-eof'])
        manifest = json.loads((folder/'plugin.json').read_text())
        self.assertEqual(manifest['api_version'], 2)
        self.assertEqual(manifest['flags'], [])

    def test_other_archive_or_store_id_does_not_receive_protondb_helper(self):
        digest = '90a3453ac02709cad64096e7539fd8141fa56f99ae3441fc24a4990dc9684358'
        self.assertEqual(frame_decky_store.apply_script(14, '0'*64), frame_decky_store.APPLY)
        self.assertEqual(frame_decky_store.apply_script(15, digest), frame_decky_store.APPLY)
        self.assertIn('FRAMEY_PROTONDB_IPC_SOURCE =', frame_decky_store.apply_script(14, digest))
