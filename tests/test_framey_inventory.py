"""Malformed peer metadata cannot hide the rest of the Decky inventory."""
import sandbox  # noqa: F401
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'ui'))
import frame_decky


class PluginInventory(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.plugins = self.home/'.local/share/frame-control/decky/plugins'
        self.plugins.mkdir(parents=True)
        self.first = self.plugin('00-first', 'First', 42, 'a'*64)
        self.middle = self.plugin('10-middle', 'Middle', 43, 'b'*64)
        self.last = self.plugin('20-last', 'Last', 44, 'c'*64)

    def plugin(self, folder, name, store_id, digest):
        path = self.plugins/folder
        path.mkdir()
        (path/'plugin.json').write_text(json.dumps({'name':name,'author':'Author'}))
        (path/'.frame-control-store.json').write_text(json.dumps(
            {'storeId':store_id,'sha256':digest,'version':'1.0','compatShims':['known-shim']}))
        return path

    def scan(self):
        # This is the actual remote inventory command in a disposable home;
        # no service, SSH, Steam CEF, store download or headset is involved.
        def ssh(command, stdin=None, **kwargs):
            self.assertEqual(command,'python3 -')
            self.assertEqual(stdin,frame_decky.PLUGINS_PROBE)
            run = subprocess.run([sys.executable,'-'],input=stdin,text=True,capture_output=True,
                                 env={**os.environ,'HOME':str(self.home),'USERPROFILE':str(self.home)},timeout=10)
            self.assertEqual(run.returncode,0,run.stderr)
            return run.stdout
        return frame_decky.plugin_status(ssh)['plugins']

    def test_non_object_manifest_cannot_abort_valid_neighbor_inventory(self):
        path = self.middle/'plugin.json'
        for value in ([], ['name'], None, True, 1, 'text'):
            with self.subTest(value=value):
                original = json.dumps(value).encode()
                path.write_bytes(original)
                found = self.scan()
                self.assertEqual([p['name'] for p in found],['First','Last'])
                self.assertEqual([p['storeId'] for p in found],[42,44])
                self.assertEqual(path.read_bytes(),original,'Inventory must not repair or rewrite metadata')

    def test_non_object_receipt_keeps_plugin_visible_without_claiming_ownership(self):
        path = self.middle/'.frame-control-store.json'
        for value in ([], ['storeId'], None, True, 1, 'text'):
            with self.subTest(value=value):
                original = json.dumps(value).encode()
                path.write_bytes(original)
                found = self.scan()
                self.assertEqual([p['name'] for p in found],['First','Middle','Last'])
                self.assertEqual([p['storeId'] for p in found],[42,None,44])
                self.assertEqual(found[1]['sha256'],'')
                self.assertEqual(found[1]['version'],'')
                self.assertEqual(found[1]['compatShims'],[])
                self.assertEqual(path.read_bytes(),original)

    def test_repaired_metadata_reappears_on_fresh_read(self):
        manifest = self.middle/'plugin.json'
        receipt = self.middle/'.frame-control-store.json'
        manifest.write_text('[]')
        self.assertEqual([p['name'] for p in self.scan()],['First','Last'])
        manifest.write_text(json.dumps({'name':'Recovered','author':'Repaired author'}))
        receipt.write_text('[]')
        found = self.scan()
        self.assertEqual(found[1]['name'],'Recovered')
        self.assertIsNone(found[1]['storeId'])
        receipt.write_text(json.dumps({'storeId':43,'sha256':'d'*64,'version':'2.0'}))
        found = self.scan()
        self.assertEqual(found[1]['storeId'],43)
        self.assertEqual(found[1]['sha256'],'d'*64)
        self.assertEqual(found[1]['version'],'2.0')
        self.assertEqual(found[1]['author'],'Repaired author')

    def test_only_positive_integer_store_ids_claim_inventory_ownership(self):
        receipt = self.middle/'.frame-control-store.json'
        for value in (True, False, 0, -1, 43.0, '43', None):
            with self.subTest(value=value):
                original = json.dumps({'storeId':value,'sha256':'b'*64})
                receipt.write_text(original)
                found = self.scan()
                self.assertEqual([p['name'] for p in found], ['First','Middle','Last'])
                self.assertEqual([p['storeId'] for p in found], [42,None,44])
                self.assertEqual(receipt.read_text(), original)
        receipt.write_text(json.dumps({'storeId':43,'sha256':'b'*64}))
        self.assertEqual(self.scan()[1]['storeId'], 43)

    def test_empty_objects_keep_existing_fallbacks_and_valid_neighbors(self):
        (self.middle/'plugin.json').write_text('{}')
        (self.middle/'.frame-control-store.json').write_text('{}')
        found = self.scan()
        self.assertEqual([p['folder'] for p in found],['00-first','10-middle','20-last'])
        self.assertEqual(found[1]['name'],'10-middle')
        self.assertEqual(found[1]['author'],'')
        self.assertIsNone(found[1]['storeId'])
        self.assertEqual(found[0]['compatShims'],['known-shim'])
        self.assertEqual(found[2]['sha256'],'c'*64)


if __name__ == '__main__':
    unittest.main()
