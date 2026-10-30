"""The optional HTTP gateway must stay inside its marked disposable VM."""
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GatewayIsolation(unittest.TestCase):
    def test_host_and_wrong_guest_marker_refuse_before_commands_or_environment_changes(self):
        gateway = load('http_gateway_guard', ROOT/'tests/decky-runtime/syncthing_http.py')
        for uid, marker in [(0, 'Frame Control Flatpak VM v1\n'), (1100, 'different guest\n')]:
            with self.subTest(uid=uid, marker=marker), \
                    patch.object(gateway.os, 'getuid', return_value=uid, create=True), \
                    patch.object(gateway.Path, 'read_text', return_value=marker), \
                    patch.object(gateway.subprocess, 'Popen') as start, \
                    patch.dict(gateway.os.environ, {}, clear=True):
                with self.assertRaises(AssertionError):
                    gateway.exercise(None, 'unused.service')
                start.assert_not_called()
                self.assertEqual(dict(gateway.os.environ), {})

    def test_production_bundle_contains_unchanged_dispatch_and_catalogue_import_dependencies(self):
        driver = load('http_gateway_packer', ROOT/'scripts/framey-test-syncthing-flatpak-package.py')
        payloads, metadata = driver.http_gateway_payloads()
        with tarfile.open(fileobj=io.BytesIO(payloads['framey-http-ui.tar'])) as archive:
            names = set(archive.getnames())
            self.assertTrue({'ui/server.py', 'ui/framey_panel.py', 'ui/local-bin/ssh',
                             'ui/frame_steam.py', 'apk-catalog/build.py',
                             'apk-catalog/reports.py', 'apk-catalog/pick.py'} <= names)
            self.assertEqual(names, set(metadata['sourceSha256']))
            self.assertEqual(metadata['sourceSha256'],
                             json.loads(payloads['framey-http-ui-sources.json']))
            for member in archive:
                self.assertTrue(member.isfile())
                self.assertFalse(member.name.startswith('/'))
                self.assertNotIn('..', Path(member.name).parts)
                self.assertEqual(archive.extractfile(member).read(), (ROOT/member.name).read_bytes())
            self.assertEqual(archive.getmember('ui/local-bin/ssh').mode, 0o700)
