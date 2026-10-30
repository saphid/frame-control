"""Unreleased Syncthing ownership candidate; no official helper or service runs."""
import sandbox  # noqa: F401
import importlib.util
import logging
import os
from pathlib import Path
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
        self.owner.stop()

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
