"""Unreleased Syncthing ownership candidate; no official helper or service runs."""
import sandbox  # noqa: F401
import asyncio
import importlib.util
import logging
import os
from pathlib import Path
import runpy
import signal
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == 'linux', 'Candidate owns Linux process sessions and flocks')
class WatchdogOwnership(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        decky = types.ModuleType('decky_plugin')
        decky.logger = logging.getLogger('syncthing-candidate')
        for name in ('DIR', 'SETTINGS_DIR', 'RUNTIME_DIR', 'LOG_DIR'):
            setattr(decky, 'DECKY_PLUGIN_'+name, str(self.home))
        spec = importlib.util.spec_from_file_location('syncthing_candidate',
            ROOT/'ui/vendor/syncthing-0.2.7/main.py')
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'decky_plugin':decky}):
            spec.loader.exec_module(self.module)
        self.owner = self.module.watchdog

    async def asyncTearDown(self):
        # Failed assertions in a mocked-Popen test must never signal a real PID.
        if isinstance(self.owner.process, Mock):
            self.owner.process = None
        self.owner.stop()

    def private_http(self):
        from http.server import BaseHTTPRequestHandler
        import socketserver
        import threading
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                requests.append((self.command, self.path, dict(self.headers)))
                if self.path in ('/__decky-watchdog/check/start', '/__decky-watchdog/reload-config'):
                    # Setup and normal connected-peer shutdown exceed 5s.
                    import time
                    time.sleep(5.1)
                code, body, length = 200, b'{"privateFixture":true}', None
                if 'large' in self.path:
                    body = b'x'*(256*1024+1)
                if 'truncated' in self.path:
                    body, length = b'short', 100
                if 'redirect' in self.path:
                    code, body = 302, b''
                if self.command == 'POST':
                    code, body = 204, b''
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(length if length is not None else len(body)))
                if code == 302:
                    self.send_header('Location', 'http://127.0.0.1:1/never-follow')
                self.end_headers()
                try:
                    self.wfile.write(body)
                except BrokenPipeError:
                    pass

            do_POST = do_GET
        self.owner.runtime = tempfile.TemporaryDirectory(prefix='framey-syncthing-test-')
        server = socketserver.UnixStreamServer(str(Path(self.owner.runtime.name)/'watchdog.sock'), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def cleanup():
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        self.addCleanup(cleanup)
        self.owner.process = Mock(pid=424242)
        self.owner.process.poll.return_value = None
        return requests

    async def test_http_uses_only_private_socket_and_preserves_status_and_headers(self):
        requests = self.private_http()
        with patch.object(self.module.http.client.HTTPConnection, 'connect', side_effect=AssertionError('TCP fallback')):
            response = self.owner.fetch('GET', '/rest/system/status?folder=private%20fixture',
                                        {'Accept':'application/json','X-API-Key':'private-fixture'})
            self.assertEqual(response['status'], 200)
            self.assertEqual(response['body'], '{"privateFixture":true}')
            self.assertEqual(response['headers']['content-type'], 'application/json')
            self.assertEqual(requests[-1][:2], ('GET','/rest/system/status?folder=private%20fixture'))
            self.assertEqual(requests[-1][2]['x-api-key'], 'private-fixture')
            self.assertEqual(self.owner.fetch('POST', '/__decky-watchdog/start', {})['status'], 204)

    async def test_http_rejects_other_origins_paths_methods_and_headers_before_io(self):
        requests = self.private_http()
        for method,path,headers in [
                ('GET','http://127.0.0.1:58384/rest/system/status',{}),
                ('GET','//other/rest/system/status',{}), ('GET','/rest/../private',{}),
                ('GET','/rest/%73ystem/status',{}), ('GET','/rest/system/status#fragment',{}),
                ('GET','/rest/system/status\r\nHost: other',{}), ('GET','/rest\\system/status',{}),
                ('DELETE','/rest/system/status',{}), ('POST','/rest/system/status',{}),
                ('GET','/rest/system/status',{'Host':'other'}),
                ('GET','/rest/system/status',{'authorization':'private\r\nInjected: fixture'}),
                ('GET','/rest/system/status',{'Accept':'a','accept':'b'}),
                ('GET','/rest/system/status',{'X-API-Key':'x'*4097})]:
            with self.subTest(method=method,path=path), self.assertRaises(ValueError):
                self.owner.fetch(method,path,headers)
        self.assertEqual(requests, [])

    async def test_http_size_truncation_and_redirect_boundaries(self):
        requests = self.private_http()
        for mode in ('large','truncated'):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.owner.fetch('GET','/rest/system/status?'+mode,{})
        before = len(requests)
        self.assertEqual(self.owner.fetch('GET','/rest/system/status?redirect',{})['status'], 302)
        self.assertEqual(len(requests), before+1)

    async def test_http_without_live_owned_socket_never_falls_back_to_tcp(self):
        self.owner.runtime = tempfile.TemporaryDirectory(prefix='framey-syncthing-test-')
        self.owner.process = Mock(pid=424242)
        self.owner.process.poll.return_value = None
        with patch.object(self.module.http.client.HTTPConnection, 'connect', side_effect=AssertionError('TCP fallback')):
            with self.assertRaises(FileNotFoundError):
                self.owner.fetch('GET','/rest/system/status',{})
            self.owner.closed = True
            with self.assertRaises(RuntimeError):
                self.owner.fetch('GET','/rest/system/status',{})

    async def test_setup_check_can_outlast_normal_socket_timeout(self):
        self.private_http()
        response = self.owner.fetch('POST', '/__decky-watchdog/check/start', {})
        self.assertEqual(response['status'], 204)

    async def test_service_transition_can_outlast_normal_socket_timeout(self):
        self.private_http()
        response = self.owner.fetch('POST', '/__decky-watchdog/reload-config', {})
        self.assertEqual(response['status'], 204)

    async def test_only_service_lifecycle_calls_receive_longer_socket_budget(self):
        self.owner.runtime = tempfile.TemporaryDirectory(prefix='framey-syncthing-test-')
        self.owner.process = Mock(pid=424242)
        self.owner.process.poll.return_value = None
        with patch.object(self.module.http.client, 'HTTPConnection') as connection, \
                patch.object(self.module.socket, 'socket') as stream:
            response = connection.return_value.getresponse.return_value
            response.read.return_value = b''
            response.length = 0
            response.getheader.return_value = ''
            for method, path, budget in [
                    ('POST', '/__decky-watchdog/'+route, 20)
                    for route in ('start', 'stop', 'reload-config', 'check/start')]+[
                    ('GET', '/__decky-watchdog/state', 5),
                    ('GET', '/rest/system/version', 5),
                    ('POST', '/__decky-watchdog/check/scan_port', 5),
                    ('POST', '/', 5)]:
                with self.subTest(method=method, path=path):
                    self.owner.fetch(method, path, {})
                    connection.assert_called_with('localhost', timeout=budget)
                    stream.return_value.settimeout.assert_called_with(budget)

    def test_service_vm_bootstrap_refuses_host_before_any_commands(self):
        # Even UID 0 must fail outside the owned guest, without reaching the
        # guest-only service or shutdown commands in its exception path.
        with patch('os.getuid', return_value=0), \
                patch('pathlib.Path.is_file', return_value=False), \
                patch('subprocess.run') as command:
            with self.assertRaisesRegex(RuntimeError, 'only inside the owned service VM'):
                runpy.run_path(str(ROOT/'tests/decky-runtime/syncthing_service_root.py'))
            command.assert_not_called()

    def test_package_vm_bootstrap_refuses_host_before_any_commands(self):
        with patch('os.getuid', return_value=0), \
                patch('pathlib.Path.is_file', return_value=False), \
                patch('subprocess.run') as command:
            with self.assertRaisesRegex(RuntimeError, 'Only the private Flatpak VM'):
                runpy.run_path(str(ROOT/'tests/decky-runtime/syncthing_flatpak_package_root.py'))
            command.assert_not_called()

    async def test_http_rpc_caps_concurrent_requests(self):
        self.owner.http_inflight = 4
        with self.assertRaisesRegex(ValueError, 'Too many'):
            await self.module.Plugin.framey_http_fetch(self.module.Plugin, 'GET','/rest/system/status',{})
        self.assertEqual(self.owner.http_inflight, 4)

    async def test_cancelled_rpc_retains_slot_until_socket_worker_finishes(self):
        entered, release = asyncio.Event(), asyncio.Event()
        workers = []
        async def private_worker(*_args):
            workers.append(asyncio.current_task())
            if len(workers) == 4:
                entered.set()
            await release.wait()
            raise RuntimeError('Abandoned fixture response')
        with patch.object(self.module.asyncio, 'to_thread', side_effect=private_worker):
            requests = [asyncio.create_task(self.module.Plugin.framey_http_fetch(
                self.module.Plugin, 'GET', '/rest/system/status', {})) for _ in range(4)]
            try:
                await asyncio.wait_for(entered.wait(), 2)
                for request in requests:
                    request.cancel()
                await asyncio.gather(*requests, return_exceptions=True)
                self.assertEqual(self.owner.http_inflight, 4)
                with self.assertRaisesRegex(ValueError, 'Too many'):
                    await self.module.Plugin.framey_http_fetch(
                        self.module.Plugin, 'GET', '/rest/system/status', {})
                self.assertTrue(all(not worker.done() for worker in workers))
            finally:
                release.set()
                await asyncio.gather(*requests, *workers, return_exceptions=True)
            self.assertEqual(self.owner.http_inflight, 0)

    async def test_reset_without_owned_handle_never_spawns_a_name_wide_killer(self):
        with patch.object(self.module.subprocess, 'Popen') as spawn:
            await self.module.reset_all_processes()
        spawn.assert_not_called()

    async def test_stop_reaps_owned_session_and_preserves_unrelated_process(self):
        owned = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
        unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        self.owner.process = owned
        try:
            await self.module.reset_all_processes()
            self.assertIsNotNone(owned.returncode)
            self.assertIsNone(unrelated.poll())
            self.assertIsNone(self.owner.process)
        finally:
            for child in (owned, unrelated):
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=5)

    async def test_stubborn_owned_child_is_killed_and_reaped(self):
        child = Mock(pid=424242)
        child.poll.return_value = None
        child.wait.side_effect = [subprocess.TimeoutExpired('owned child', 2), 0]
        self.owner.process = child
        with patch.object(self.module.os, 'killpg') as kill:
            self.owner.stop()
        self.assertEqual(kill.call_args_list,
            [unittest.mock.call(child.pid, signal.SIGTERM), unittest.mock.call(child.pid, signal.SIGKILL)])
        self.assertEqual(child.wait.call_args_list,
            [unittest.mock.call(timeout=2), unittest.mock.call(timeout=1)])
        self.assertIsNone(self.owner.process)

    async def test_failed_reap_keeps_handle_and_prevents_replacement(self):
        child = Mock(pid=424242)
        child.poll.return_value = None
        child.wait.side_effect = subprocess.TimeoutExpired('owned child', 1)
        self.owner.process = child
        try:
            with patch.object(self.module.os, 'killpg'), self.assertRaises(subprocess.TimeoutExpired):
                self.owner.stop()
            self.assertIs(self.owner.process, child)
            with patch.object(self.module.subprocess, 'Popen') as spawn:
                self.owner.start()
                spawn.assert_not_called()
        finally:
            self.owner.process = None

    async def test_repeated_main_has_one_child_and_unload_blocks_late_restart(self):
        child = Mock(pid=424242)
        child.poll.return_value = None
        with patch.object(self.module.subprocess, 'Popen', return_value=child) as spawn:
            await self.module.Plugin._main(self.module.Plugin)
            await self.module.Plugin._main(self.module.Plugin)
            self.assertEqual(spawn.call_count, 1)
            with patch.object(self.module.os, 'killpg'):
                await self.module.Plugin._unload(self.module.Plugin)
            with self.assertRaisesRegex(RuntimeError, 'unloaded'):
                self.module.start_watchdog()
            self.assertIsNone(self.owner.process)

    async def test_child_environment_and_session_are_scoped(self):
        child = Mock()
        child.poll.return_value = None
        with patch.dict(os.environ, {'LD_LIBRARY_PATH':'private-loader-libraries'}, clear=True), \
                patch.object(self.module.subprocess, 'Popen', return_value=child) as spawn:
            self.owner.start()
            command = spawn.call_args.args[0]
            options = spawn.call_args.kwargs
            self.assertEqual(command, [self.module.WATCHDOG_BIN_PATH, self.module.SETTINGS_PATH,
                                      self.module.WATCHDOG_PID_PATH, str(self.home)])
            self.assertTrue(options['start_new_session'])
            self.assertEqual(options['env']['LD_LIBRARY_PATH'], '')
            self.assertEqual(options['env']['DBUS_SESSION_BUS_ADDRESS'], f'unix:path=/run/user/{os.getuid()}/bus')
        self.owner.process = None

    async def test_pid_cleanup_preserves_foreign_file_and_a_locked_successor(self):
        import fcntl
        pid_path = self.module.WATCHDOG_PID_PATH
        lock_path = pid_path.with_suffix('.framey-lock')
        lock_path.touch()
        pid_path.write_text('not owned')
        self.owner.clean_pid(424242)
        self.assertEqual(pid_path.read_text(), 'not owned')
        pid_path.write_text('424242')
        with lock_path.open('r+b') as successor:
            fcntl.flock(successor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.owner.clean_pid(424242)
            self.assertTrue(pid_path.exists())
        self.owner.clean_pid(424242)
        self.assertFalse(pid_path.exists())
        self.assertTrue(lock_path.is_file())

    async def test_legacy_migration_does_not_find_or_signal_external_processes(self):
        old = dict(config_version=1, autostart=False, flatpak_name='', port=8384, api_key='',
                   basic_auth_user='', basic_auth_pass='', keep_running_on_desktop=False)
        with patch.object(self.module.subprocess, 'Popen') as spawn:
            migrated = await self.module.migrate_settings_v2(old)
        spawn.assert_not_called()
        self.assertEqual(migrated['is_setup'], 'migratingV2')
        self.assertEqual(migrated['config_version'], 2)


if __name__ == '__main__':
    unittest.main()
