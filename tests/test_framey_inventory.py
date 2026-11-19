"""Malformed peer metadata cannot hide the rest of the Decky inventory."""
import sandbox  # noqa: F401
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

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

    def test_oversized_receipt_cannot_claim_ownership_or_hide_valid_neighbors(self):
        receipt = self.middle/'.frame-control-store.json'
        record = json.dumps({'storeId':43,'sha256':'b'*64,'version':'1.0',
                             'compatShims':['known-shim']}).encode()
        for size in (16_385, 200_000):
            with self.subTest(size=size):
                original = record + b' '*(size-len(record))
                receipt.write_bytes(original)
                found = self.scan()
                self.assertEqual([p['name'] for p in found], ['First','Middle','Last'])
                self.assertEqual([p['storeId'] for p in found], [42,None,44])
                self.assertEqual(found[1]['sha256'], '')
                self.assertEqual(found[1]['version'], '')
                self.assertEqual(found[1]['compatShims'], [])
                self.assertEqual(receipt.read_bytes(), original)
        # The limit includes its boundary; fresh scans recover after repair.
        original = record + b' '*(16_384-len(record))
        receipt.write_bytes(original)
        found = self.scan()
        self.assertEqual([p['storeId'] for p in found], [42,43,44])
        self.assertEqual(found[1]['sha256'], 'b'*64)
        self.assertEqual(found[1]['compatShims'], ['known-shim'])
        self.assertEqual(receipt.read_bytes(), original)

    def test_oversized_receipt_is_rejected_before_reading_its_contents(self):
        receipt = self.middle/'.frame-control-store.json'
        receipt.write_bytes(b' '*16_385)
        namespace = {'json':json}
        exec(frame_decky.PLUGIN_SCAN, namespace)
        original_read = Path.open

        def open_file(path, *args, **kwargs):
            if path == receipt:
                self.fail('Oversized receipt contents were read')
            return original_read(path, *args, **kwargs)

        with patch.object(Path, 'open', open_file):
            found = namespace['plugins'](self.plugins)
        self.assertEqual([p['storeId'] for p in found], [42,None,44])

    def local_scan(self):
        namespace = {'json': json}
        exec(frame_decky.PLUGIN_SCAN, namespace)
        return namespace['plugins'](self.plugins)

    def metadata_snapshot(self):
        return {str(path.relative_to(self.plugins)): path.read_bytes()
                for path in self.plugins.rglob('*') if path.is_file()}

    def test_receipt_and_manifest_limits_count_utf8_bytes_at_the_boundary(self):
        for name in ('.frame-control-store.json', 'plugin.json'):
            path = self.middle/name
            original = path.read_bytes()
            record = (json.dumps({'storeId': 43, 'sha256': 'b'*64, 'name': 'Middle',
                                  'author': 'Author', 'note': '\u65e5'}, ensure_ascii=False)).encode('utf-8')
            for size in (16_384, 16_385):
                with self.subTest(name=name, size=size):
                    path.write_bytes(record+b' '*(size-len(record)))
                    before = self.metadata_snapshot()
                    found = self.local_scan()
                    if size == 16_384:
                        self.assertEqual([p['storeId'] for p in found], [42, 43, 44])
                        self.assertEqual(found[1]['name'], 'Middle')
                    elif name == 'plugin.json':
                        self.assertEqual([p['storeId'] for p in found], [42, 44])
                    else:
                        self.assertEqual([p['storeId'] for p in found], [42, None, 44])
                    self.assertEqual(self.metadata_snapshot(), before)
            path.write_bytes(original)

    def test_growing_metadata_is_bounded_and_cannot_claim_ownership_or_identity(self):
        for name in ('.frame-control-store.json', 'plugin.json'):
            with self.subTest(name=name):
                path = self.middle/name
                original = path.read_bytes()
                before = self.metadata_snapshot()
                grown = (original+b' '*(2*1024*1024) if name != 'plugin.json' else
                         json.dumps({'name': 'X'*(1024*1024), 'author': 'Author'}).encode())
                original_stat, original_open = Path.stat, Path.open
                growth, reads = [], []

                class SizeSnapshot:
                    def __init__(self, actual):
                        self.actual = actual
                    def __getattr__(self, key):
                        return getattr(self.actual, key)
                    @property
                    def st_size(self):
                        if not growth:
                            path.write_bytes(grown)
                            growth.append(True)
                        return self.actual.st_size

                def stat(candidate, *args, **kwargs):
                    actual = original_stat(candidate, *args, **kwargs)
                    return SizeSnapshot(actual) if candidate == path else actual

                class ObservedRead:
                    def __init__(self, stream):
                        self.stream = stream
                    def __enter__(self):
                        return self
                    def __exit__(self, *args):
                        return self.stream.__exit__(*args)
                    def read(self, size=-1):
                        value = self.stream.read(size)
                        reads.append((size, len(value if isinstance(value, bytes) else value.encode('utf-8'))))
                        return value
                    def __getattr__(self, key):
                        return getattr(self.stream, key)

                def open_file(candidate, *args, **kwargs):
                    stream = original_open(candidate, *args, **kwargs)
                    mode = args[0] if args else kwargs.get('mode', 'r')
                    return ObservedRead(stream) if candidate == path and mode.startswith('r') else stream

                with patch.object(Path, 'stat', stat), patch.object(Path, 'open', open_file):
                    found = self.local_scan()
                self.assertEqual(growth, [True], 'fixture must grow after the real size snapshot')
                self.assertEqual(reads, [(16_385, 16_385)], 'read at most one byte beyond the 16 KiB limit')
                self.assertEqual([p['storeId'] for p in found],
                                 [42, 44] if name == 'plugin.json' else [42, None, 44])
                if name != 'plugin.json':
                    self.assertEqual(found[1]['sha256'], '')
                    self.assertEqual(found[1]['version'], '')
                    self.assertEqual(found[1]['compatShims'], [])
                after = self.metadata_snapshot()
                key = str(path.relative_to(self.plugins))
                self.assertEqual(after.pop(key), grown)
                before.pop(key)
                self.assertEqual(after, before, 'metadata admission must preserve every peer byte')
                path.write_bytes(original)

    def test_malformed_utf8_or_json_is_contained_to_its_metadata_file(self):
        for name in ('.frame-control-store.json', 'plugin.json'):
            path = self.middle/name
            original = path.read_bytes()
            for invalid in (b'\xff', b'{"name":', b'\xef\xbb\xbf{}'):
                with self.subTest(name=name, invalid=invalid):
                    path.write_bytes(invalid)
                    before = self.metadata_snapshot()
                    found = self.local_scan()
                    self.assertEqual([p['storeId'] for p in found],
                                     [42, 44] if name == 'plugin.json' else [42, None, 44])
                    self.assertEqual(self.metadata_snapshot(), before)
            path.write_bytes(original)

    def test_disappearing_manifest_does_not_abort_valid_neighbors(self):
        manifest = self.middle/'plugin.json'
        before = self.metadata_snapshot()
        original_stat = Path.stat
        removed = []
        def stat(path, *args, **kwargs):
            snapshot = original_stat(path, *args, **kwargs)
            if path == manifest and kwargs.get('follow_symlinks', True) and not removed:
                manifest.unlink()
                removed.append(True)
            return snapshot
        with patch.object(Path, 'stat', stat):
            found = self.local_scan()
        self.assertEqual(removed, [True])
        self.assertEqual([p['storeId'] for p in found], [42, 44])
        before.pop(str(manifest.relative_to(self.plugins)))
        self.assertEqual(self.metadata_snapshot(), before)

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
