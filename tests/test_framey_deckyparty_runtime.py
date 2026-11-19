"""A reload is tied to process identities; warning retries are not new plugins."""
import sandbox  # noqa: F401
import importlib.util
import os
from pathlib import Path
import signal
import socket
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('deckyparty_runtime_probe', ROOT/'tests/decky-runtime/deckyparty_private.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


@unittest.skipIf(os.name == 'nt', 'private Linux reload fixture uses Unix sockets')
class ReloadObservation(unittest.TestCase):
    def run_reload(self, warnings, *, regression, unloaded=False, orphan=False, old_survives=False):
        # Keep AF_UNIX paths below macOS's short socket-path limit.
        with tempfile.TemporaryDirectory(prefix='fcdp-', dir='/tmp') as directory:
            root = Path(directory)
            log = root/'runtime.log'
            log.write_text('[loader][INFO]: Loaded DeckyParty File Manager\n')
            peer_path = root/'plugin_socket_private'
            listener = socket.socket(socket.AF_UNIX)
            self.addCleanup(listener.close)
            listener.bind(str(peer_path))
            listener.listen(1)
            after_rpc = False
            original = {22: dict(state='S', parent=21, start='old-plugin'),
                        21: dict(state='S', parent=10, start='fork-server'),
                        10: dict(state='S', parent=9, start='loader-child'),
                        54: dict(state='S', parent=22, start='old-server')}

            def identity(pid):
                if after_rpc and pid == 22 and not old_survives:
                    return None
                if after_rpc and pid == 54:
                    return dict(state='S', parent=1, start='old-server') if orphan else None
                if pid == 91:
                    return dict(state='S', parent=21, start='replacement-plugin')
                return original.get(pid)

            def paths(value):
                if value == '/proc':
                    return SimpleNamespace(iterdir=lambda: [SimpleNamespace(name='91')])
                if value == '/tmp':
                    return SimpleNamespace(glob=lambda pattern: [peer_path])
                return Path(value)

            def rpc(method, plugin):
                nonlocal after_rpc
                self.assertEqual((method, plugin), ('loader/reload_plugin', 'DeckyParty File Manager'))
                after_rpc = True
                with log.open('a') as stream:
                    stream.write('[plugin][WARNING]: Plugin DeckyParty File Manager still alive 5 seconds after stop request! Sending SIGKILL!\n'*warnings)
                    if unloaded:
                        stream.write('Unloaded DeckyParty File Manager\n')
                    stream.write('[loader][INFO]: Loaded DeckyParty File Manager\n')

            def ready(predicate, description):
                result = predicate()
                self.assertTrue(result, description)
                return result

            def servers():
                return [54] if not after_rpc or orphan else []

            with patch.object(probe, 'Path', side_effect=paths), \
                    patch.object(probe, 'identity', side_effect=identity), \
                    patch.object(probe.os, 'getpgid', return_value=54), \
                    patch.object(probe.os, 'killpg') as kill, \
                    patch.object(probe.time, 'sleep'):
                result = probe.reload(SimpleNamespace(pid=9), SimpleNamespace(name=str(log)),
                                      servers, rpc, ready, 0, regression=regression)
            self.assertEqual(result['forcedPluginKills'], warnings)
            self.assertEqual(result['exactPluginChildrenRemaining'], {})
            self.assertEqual(list(result['pluginChildrenAfter']), [91])
            self.assertEqual(result['fixtureClosedUnixPeers'], [str(peer_path)])
            self.assertEqual(result['unloadHookCompleted'], unloaded)
            if regression and orphan:
                kill.assert_called_once_with(54, signal.SIGTERM)
                self.assertEqual(result['testCleanupSignaledOwnedServers'], [54])
            else:
                kill.assert_not_called()
            return result

    def test_negative_requires_a_forced_stop_but_allows_retry_warnings(self):
        for warnings in (1, 2):
            with self.subTest(warnings=warnings):
                self.run_reload(warnings, regression=True, orphan=True)
        with self.assertRaises(AssertionError):
            self.run_reload(0, regression=True, orphan=True)

    def test_negative_still_rejects_live_original_plugin_and_completed_unload(self):
        for options in ({'old_survives': True}, {'unloaded': True}):
            with self.subTest(options=options), self.assertRaises(AssertionError):
                self.run_reload(2, regression=True, orphan=True, **options)

    def test_clean_reload_still_requires_no_forced_warnings(self):
        self.run_reload(0, regression=False, unloaded=True)
        for warnings in (1, 2):
            with self.subTest(warnings=warnings), self.assertRaises(AssertionError):
                self.run_reload(warnings, regression=False, unloaded=True)

    def test_clean_reload_still_rejects_orphan_and_live_plugin_and_missing_unload(self):
        for options in ({'orphan': True, 'unloaded': True},
                        {'old_survives': True, 'unloaded': True}, {}):
            with self.subTest(options=options), self.assertRaises(AssertionError):
                self.run_reload(0, regression=False, **options)


if __name__ == '__main__':
    unittest.main()
