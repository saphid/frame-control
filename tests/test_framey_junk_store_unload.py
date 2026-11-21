"""Exact managed Junk-Store 1.1.13 install, archive preservation and clean unload."""
import sandbox  # noqa: F401
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile

import framey_official
import test_frame_decky_store as transactions
import frame_decky_store

ROOT = Path(__file__).resolve().parents[1]
OLD_STOP = (
    b'            # Stop the event loop if it exists\n'
    b'            if Helper.ws_loop and Helper.ws_loop.is_running():\n'
    b'                Helper.ws_loop.stop()\n'
)
NEW_STOP = b"            # Leave Decky's shared event loop running during plugin unload.\n"
OLD_CANCEL = (
    b'            # Cancel all pending asyncio tasks\n'
    b'            tasks = [task for task in asyncio.all_tasks() if not task.done()]\n'
    b'            if tasks:\n'
    b'                decky_plugin.logger.info(f"Cancelling {len(tasks)} pending tasks...")\n'
    b'                for task in tasks:\n'
    b'                    task.cancel()\n'
    b'                # Wait for all tasks to complete cancellation\n'
    b'                await asyncio.gather(*tasks, return_exceptions=True)\n'
)
NEW_CANCEL = b"            # Leave Decky's shared IPC and unload tasks intact.\n"
PREFIX = (b'from framey_decky_ipc import install as _framey_install_ipc_eof\n'
          b'_framey_install_ipc_eof()\ndel _framey_install_ipc_eof\n')


@unittest.skipIf(os.name == 'nt', 'remote plugin transaction requires POSIX')
class JunkStoreUnload(unittest.TestCase):
    def setUp(self):
        self.tx = transactions.StoreTransaction()
        self.tx.setUp()
        self.addCleanup(self.tx.doCleanups)
        self.pin = next(p for p in framey_official.PLUGINS if p['id'] == 84)
        self.data = framey_official.archive(self.pin)
        self.folder = self.tx.folder.parent / self.pin['folder']

    def install(self, **kwargs):
        return self.tx.apply('install', self.data, plugin_id=84, folder=self.pin['folder'],
                             version=self.pin['version'], **kwargs)

    def test_only_unload_blocks_and_ipc_adapter_change(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        with zipfile.ZipFile(io.BytesIO(self.data)) as z:
            for member in z.infolist():
                if member.is_dir():
                    continue
                relative = member.filename.split('/', 1)[1]
                expected = z.read(member)
                if relative == 'main.py':
                    expected = PREFIX + expected.replace(OLD_STOP, NEW_STOP).replace(OLD_CANCEL, NEW_CANCEL)
                self.assertEqual((self.folder / relative).read_bytes(), expected, relative)
        self.assertEqual(
            (self.folder / 'py_modules/framey_decky_ipc.py').read_bytes(),
            (ROOT / 'ui/framey_decky_ipc.py').read_bytes(),
        )
        self.assertTrue((self.folder / 'scripts/junk-store.sh').stat().st_mode & 0o100)
        receipt = json.loads((self.folder / '.frame-control-store.json').read_text())
        self.assertEqual(receipt['compatShims'], ['junk-store-clean-unload', 'junk-store-ipc-eof'])

    def test_missing_adapter_fails_before_publishing(self):
        with patch.object(frame_decky_store, 'apply_script', return_value=frame_decky_store.APPLY):
            result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Missing Junk-Store IPC helper', result.stderr)
        self.assertFalse(self.folder.exists())

    def test_other_identity_or_digest_gets_no_helper(self):
        self.assertEqual(frame_decky_store.apply_script(84, '0' * 64), frame_decky_store.APPLY)
        self.assertEqual(frame_decky_store.apply_script(85, self.pin['sha256']), frame_decky_store.APPLY)

    def test_wrong_folder_is_rejected(self):
        result = self.tx.apply('install', self.data, plugin_id=84, folder='OtherJunkStore',
                               version=self.pin['version'])
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.folder.exists())

    def test_old_receipt_requires_update_until_both_shims_present(self):
        import framey_compatibility
        for shims in ([], ['junk-store-clean-unload'], ['junk-store-ipc-eof']):
            old = framey_compatibility.lookup(84, self.pin['sha256'], self.pin['version'], installed_shims=shims)
            self.assertEqual(old['status'], 'partial', shims)
            self.assertIn('Update or reinstall', old['reason'])
        fixed = framey_compatibility.lookup(
            84, self.pin['sha256'], self.pin['version'],
            installed_shims=['junk-store-clean-unload', 'junk-store-ipc-eof'],
        )
        self.assertEqual(fixed['status'], 'partial')
        self.assertNotIn('Update or reinstall', fixed['reason'])


if __name__ == '__main__':
    unittest.main()
