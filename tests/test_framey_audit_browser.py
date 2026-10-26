"""The local frontend audit still renders receipt-bound Framey panels."""
import sandbox  # noqa: F401
import base64
import hashlib
import importlib.util
import io
from pathlib import Path
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
        data = stream.getvalue()
        digest = hashlib.sha256(data).hexdigest()
        record = {'id':42, 'folder':'Example', 'sha256':digest}
        page = audit.render_panel(record, data)
        self.assertIn(base64.b64encode(bundle), page)
        self.assertIn(f'/framey/module/42/{digest}/index.js'.encode(), page)
        self.assertIn(b'const report=(kind,message)', page)
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            audit.render_panel({**record, 'sha256':'0'*64}, data)
