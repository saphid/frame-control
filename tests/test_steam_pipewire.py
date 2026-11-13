"""PC-only Steam helper tests. All app launches and KDE calls are mocked.
No portal, interactive Wayland session, Steam installation or Frame is used.
"""
import sandbox  # noqa: F401
import contextlib
import http.client
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ui'))
import frame_steam_pipewire as helper
import server

ENV = {'XDG_SESSION_TYPE': 'wayland', 'WAYLAND_DISPLAY': 'wayland-0',
       'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/mock/session-bus', 'XDG_CURRENT_DESKTOP': 'KDE'}


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        patches = [mock.patch.dict(os.environ, ENV, clear=True),
                   mock.patch.object(helper.sys, 'platform', 'linux'),
                   mock.patch.object(helper.os, 'geteuid', return_value=1000, create=True),
                   mock.patch.object(helper.Path, 'exists', return_value=False),
                   mock.patch.object(helper, '_launch', None),
                   mock.patch.object(helper, '_steam_running', return_value=False),
                   mock.patch.object(helper.shutil, 'which', side_effect=lambda n: '/usr/bin/' + n),
                   mock.patch.object(helper.subprocess, 'Popen'),
                   mock.patch.object(helper.subprocess, 'run')]
        started = [self.stack.enter_context(p) for p in patches]
        self.running, self.which, self.spawn, self.run = started[-4:]
        self.spawn.return_value.poll.return_value = None
        self.spawn.return_value.wait.side_effect = subprocess.TimeoutExpired('app', 1)
        self.run.return_value = subprocess.CompletedProcess([], 0, 'kcm_app-permissions - Application Permissions\n', '')

    def action(self, action):
        return helper.action({'action': action, 'confirmed': True})

    def test_status_is_read_only(self):
        self.assertTrue(helper.status()['available'])
        self.spawn.assert_not_called()
        self.run.assert_not_called()
        self.running.assert_not_called()

    def test_platform_and_local_session_gates(self):
        for platform in ('win32', 'darwin'):
            with self.subTest(platform=platform), mock.patch.object(helper.sys, 'platform', platform):
                self.assertFalse(helper.status()['available'])
                with self.assertRaises(helper.HelperError):
                    self.action('launch')
        for change in ({'FRAME_LOCAL': '1'}, {'XDG_SESSION_TYPE': 'x11'}, {'WAYLAND_DISPLAY': ''},
                       {'DBUS_SESSION_BUS_ADDRESS': ''}, {'SSH_CONNECTION': 'remote'}, {'SSH_CLIENT': 'remote'}):
            with self.subTest(change=change), mock.patch.dict(os.environ, change):
                for action in ('launch', 'permissions'):
                    with self.assertRaises(helper.HelperError):
                        self.action(action)
        self.spawn.assert_not_called()
        self.run.assert_not_called()

    def test_root_and_sandbox_refused(self):
        with mock.patch.object(helper.os, 'geteuid', return_value=0):
            self.assertIn('not root', helper.status()['reason'])
        with mock.patch.object(helper.Path, 'exists', return_value=True):
            with self.assertRaisesRegex(helper.HelperError, 'sandbox'):
                self.action('launch')
        self.spawn.assert_not_called()

    def test_only_explicit_supported_actions(self):
        for body in ({}, {'action': 'launch'}, {'action': 'permissions', 'confirmed': 'true'},
                     {'action': 'delete-all', 'confirmed': True}):
            with self.subTest(body=body), self.assertRaises(helper.HelperError):
                helper.action(body)
        self.spawn.assert_not_called()
        self.run.assert_not_called()

    def test_launch_exact_command_and_duplicate_guard(self):
        result = self.action('launch')
        self.assertTrue(result['launched'])
        self.assertIn('does not confirm', result['message'])
        self.spawn.assert_called_once_with(['/usr/bin/steam', '-pipewire'], stdin=subprocess.DEVNULL,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                          start_new_session=True)
        with self.assertRaisesRegex(helper.HelperError, 'already running or starting'):
            self.action('launch')
        self.assertEqual(self.spawn.call_count, 1)
        self.run.assert_not_called()

    def test_running_and_unknown_steam_fail_closed(self):
        self.running.return_value = True
        with self.assertRaisesRegex(helper.HelperError, 'Steam > Exit'):
            self.action('launch')
        self.running.side_effect = helper.HelperError('Cannot verify')
        with self.assertRaisesRegex(helper.HelperError, 'Cannot verify'):
            self.action('launch')
        self.spawn.assert_not_called()

    def test_missing_launcher_does_not_guess_flatpak(self):
        self.which.side_effect = None
        self.which.return_value = None
        with self.assertRaisesRegex(helper.HelperError, 'Flatpak-only'):
            self.action('launch')
        self.spawn.assert_not_called()

    def test_launch_error_is_not_success(self):
        self.spawn.side_effect = OSError('missing')
        with self.assertRaisesRegex(helper.HelperError, 'Could not start'):
            self.action('launch')

    def test_immediate_application_failure_is_not_success(self):
        self.spawn.return_value.wait.side_effect = None
        self.spawn.return_value.wait.return_value = 1
        for action in ('launch', 'permissions'):
            with self.subTest(action=action), mock.patch.object(helper, '_launch', None):
                with self.assertRaisesRegex(helper.HelperError, 'exited with an error'):
                    self.action(action)

    def test_permissions_opens_only_verified_exact_module_never_resets(self):
        result = self.action('permissions')
        self.assertTrue(result['opened'])
        self.assertFalse(result['reset'])
        self.assertIn('No permission was changed', result['message'])
        self.run.assert_called_once_with(['/usr/bin/kcmshell6', '--list'], capture_output=True,
                                         text=True, timeout=5, stdin=subprocess.DEVNULL)
        self.assertEqual(self.spawn.call_args.args[0], ['/usr/bin/kcmshell6', 'kcm_app-permissions'])
        self.running.assert_not_called()

    def test_wrong_module_missing_tool_and_other_desktops_only_give_guidance(self):
        for listing in ('kcm_flatpak - Flatpak Permissions', 'evil_kcm_app-permissions - nope', ''):
            self.run.return_value.stdout = listing
            result = self.action('permissions')
            self.assertFalse(result['reset'])
            self.assertFalse(result['opened'])
        self.which.side_effect = None
        self.which.return_value = None
        self.assertFalse(self.action('permissions')['opened'])
        self.which.reset_mock()
        with mock.patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': 'GNOME'}):
            self.assertFalse(self.action('permissions')['opened'])
            self.which.assert_not_called()
        self.spawn.assert_not_called()

    def test_module_listing_error_or_timeout_is_guidance_not_reset(self):
        for error in (OSError('missing'), subprocess.TimeoutExpired('kcm', 5)):
            self.run.side_effect = error
            result = self.action('permissions')
            self.assertFalse(result['opened'])
            self.assertFalse(result['reset'])
            self.assertIn('kde-config-flatpak', result['message'])
        self.spawn.assert_not_called()


class ProcessTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.tmp = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.proc = Path(self.tmp)
        # Match the temp files' owner even when tests run as root or on Windows.
        self.stack.enter_context(mock.patch.object(helper.os, 'geteuid', return_value=self.proc.stat().st_uid, create=True))
        self.add('1', 'python', b'python\0server.py\0')

    def add(self, pid, comm, cmdline):
        p = self.proc / pid
        p.mkdir()
        (p / 'comm').write_text(comm)
        (p / 'cmdline').write_bytes(cmdline)

    def test_native_launcher_webhelper_and_flatpak_detected(self):
        for comm, cmd in [('steam', b'/x/steam\0'), ('bash', b'bash\0/x/steam.sh\0'),
                          ('steamwebhelper', b'/x/steamwebhelper\0'),
                          ('flatpak', b'flatpak\0run\0com.valvesoftware.Steam\0')]:
            with self.subTest(comm=comm):
                (self.proc / '1' / 'comm').write_text(comm)
                (self.proc / '1' / 'cmdline').write_bytes(cmd)
                self.assertTrue(helper._steam_running(self.proc))

    def test_unrelated_names_are_not_steam(self):
        self.add('2', 'steamdeck-tools', b'/bin/steam-tools\0')
        self.assertFalse(helper._steam_running(self.proc))

    def test_other_user_steam_is_not_this_users_instance(self):
        self.add('2', 'steam', b'steam\0')
        with mock.patch.object(helper.os, 'geteuid', return_value=self.proc.stat().st_uid + 1):
            self.assertFalse(helper._steam_running(self.proc))

    def test_exited_process_is_skipped(self):
        (self.proc / '2').mkdir()
        self.assertFalse(helper._steam_running(self.proc))

    def test_unreadable_or_missing_inventory_fails_closed(self):
        with self.assertRaisesRegex(helper.HelperError, 'Cannot verify'):
            helper._steam_running(self.proc / 'missing')
        with mock.patch.object(helper.Path, 'read_bytes', side_effect=PermissionError('denied')):
            with self.assertRaisesRegex(helper.HelperError, 'Cannot verify'):
                helper._steam_running(self.proc)


class RouteTests(unittest.TestCase):
    def test_headset_and_private_servers_never_call_helper(self):
        for local, private in ((True, False), (False, True)):
            with mock.patch.object(server, 'LOCAL', local), mock.patch.object(server, 'PRIVATE', private), \
                    mock.patch.object(helper, 'action') as action, mock.patch.object(helper, 'status') as status:
                self.assertFalse(server.steam_pipewire_state()['available'])
                with self.assertRaises(server.Failure):
                    server.steam_pipewire_action({'action': 'launch', 'confirmed': True})
                action.assert_not_called()
                status.assert_not_called()

    def test_http_guards_get_read_only_and_post_bypasses_headset_work(self):
        with ThreadingHTTPServer(('127.0.0.1', 0), server.Handler) as httpd:
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                def request(method, body=None, headers=None):
                    conn = http.client.HTTPConnection('127.0.0.1', httpd.server_port)
                    conn.request(method, '/api/steam-pipewire', json.dumps(body) if body else None, headers or {})
                    reply = conn.getresponse()
                    code, data = reply.status, json.loads(reply.read())
                    conn.close()
                    return code, data
                with mock.patch.object(server, 'LOCAL', False), mock.patch.object(server, 'PRIVATE', False), \
                        mock.patch.object(server, 'working', side_effect=AssertionError('headset work')), \
                        mock.patch.object(server, 'ssh', side_effect=AssertionError('Frame access')), \
                        mock.patch.object(helper, 'action', return_value={'reset': False}) as action, \
                        mock.patch.object(helper, 'status', return_value={'available': True}) as status:
                    self.assertEqual(request('POST', {'action': 'launch'})[0], 403)
                    self.assertEqual(request('GET')[0], 403)
                    action.assert_not_called()
                    headers = {'X-Frame-UI': server.UI_KEY, 'X-Frame-Device': 'unrelated-device'}
                    self.assertEqual(request('GET', headers=headers), (200, {'available': True}))
                    action.assert_not_called()
                    status.assert_called_once()
                    body = {'action': 'permissions', 'confirmed': True}
                    self.assertEqual(request('POST', body, headers), (200, {'reset': False}))
                    action.assert_called_once_with(body)
            finally:
                httpd.shutdown()
                thread.join()


class PageTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node exercises production page handlers')
    def test_production_page_handlers(self):
        result = subprocess.run(['node', '--test', str(ROOT / 'tests/steam_pipewire_ui.cjs')],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
