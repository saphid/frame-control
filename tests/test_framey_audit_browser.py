"""The local frontend audit still renders receipt-bound Framey panels."""
import sandbox  # noqa: F401
import base64
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
import zipfile


MODULE = Path(__file__).resolve().parents[1]/'scripts/framey-audit-browser.py'
spec = importlib.util.spec_from_file_location('framey_audit_browser', MODULE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class ReceiptBoundAudit(unittest.TestCase):
    def test_digest_checked_archive_renders_without_installed_plugin(self):
        bundle = b"import './chunks/frontend.js';"
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('Example/dist/index.js', bundle)
            archive.writestr('Example/dist/chunks/frontend.js', b'export const ready = true;')
        data = stream.getvalue()
        digest = hashlib.sha256(data).hexdigest()
        record = {'id':42, 'folder':'Example', 'sha256':digest}
        page = audit.render_panel(record, data)
        self.assertIn(base64.b64encode(bundle), page)
        self.assertIn(f'/framey/module/42/{digest}/index.js'.encode(), page)
        self.assertIn(b'const report=(kind,message)', page)
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            audit.render_panel({**record, 'sha256':'0'*64}, data)

        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            (cache/(digest+'.zip')).write_bytes(data)
            records = {42:record}
            route = f'/framey/module/42/{digest}/'
            self.assertEqual(audit.read_module_asset(route+'index.js', records, cache), bundle)
            self.assertEqual(audit.read_module_asset(route+'chunks/frontend.js', records, cache),
                             b'export const ready = true;')
            for bad in (f'/framey/module/42/{"0"*64}/index.js',
                        route+'chunks/../frontend.js', route+'other.json',
                        f'/framey/module/042/{digest}/index.js'):
                with self.subTest(bad=bad), self.assertRaises((ValueError, KeyError)):
                    audit.read_module_asset(bad, records, cache)
            (cache/(digest+'.zip')).write_bytes(data+b'changed')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                audit.read_module_asset(route+'index.js', records, cache)
