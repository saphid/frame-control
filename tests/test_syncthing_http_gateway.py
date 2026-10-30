"""The optional HTTP gateway must stay inside its marked disposable VM."""
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import unittest
from unittest.mock import Mock, patch

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


class AuthenticatedRuntimeReadiness(unittest.TestCase):
    def gateway(self):
        return load('gateway_readiness', ROOT/'tests/decky-runtime/syncthing_http.py')

    def test_too_early_and_bad_gateway_require_eventual_authenticated_success(self):
        fetch = Mock(side_effect=[{'status': 425}, {'status': 502},
                                  {'status': 200, 'body': '{"myID":"owned-fixture"}'}])
        def wait(ready, _description):
            self.assertIs(ready(), False)
            self.assertIs(ready(), False)
            return ready()
        result = self.gateway().wait_authenticated_rest(fetch, 'private-fixture-key', wait)
        self.assertEqual(result['status'], 200)
        fetch.assert_called_with('GET', '/rest/system/status', {'X-API-Key': 'private-fixture-key'})

    def test_authentication_or_unknown_http_failure_is_not_readiness(self):
        for status in (401, 403, 500, 503):
            with self.subTest(status=status), self.assertRaises(AssertionError):
                self.gateway().wait_authenticated_rest(lambda *_args: {'status': status},
                                                       'fixture', lambda ready, _description: ready())

    def test_http_success_requires_actual_runtime_identity(self):
        with self.assertRaises((AssertionError, KeyError)):
            self.gateway().wait_authenticated_rest(lambda *_args: {'status': 200, 'body': '{}'},
                                                   'fixture', lambda ready, _description: ready())
