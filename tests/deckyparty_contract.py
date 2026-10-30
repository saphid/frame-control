"""Managed DeckyParty lifecycle contracts; no server or external files are used."""
import asyncio
import importlib.util
import logging
import os
from pathlib import Path
import pwd
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

folder = Path(sys.argv.pop(1))
decky = types.ModuleType('decky_plugin')
decky.logger = logging.getLogger('deckyparty-contract')
decky.DECKY_PLUGIN_DIR = str(folder)
decky.DECKY_PLUGIN_LOG_DIR = str(folder)
decky.DECKY_PLUGIN_RUNTIME_DIR = str(folder/'private-runtime')
sys.modules['decky_plugin'] = decky
spec = importlib.util.spec_from_file_location('deckyparty', folder/'main.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Plugin = module.Plugin


class Lifecycle(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        Plugin._enabled = False
        Plugin._proc = None
        Plugin._runner_handle = None

    async def asyncTearDown(self):
        if hasattr(Plugin, '_unload'):
            await Plugin._unload(Plugin())

    async def test_actual_user_and_system_interpreter(self):
        with patch.dict(os.environ, {'USER':'root', 'DECKY_USER':'other-user'}):
            command = Plugin._build_command()
            self.assertEqual(command[:2], ['/usr/bin/python3', str(module.SCRIPT_PATH)])
            self.assertEqual(Plugin._get_user(), pwd.getpwuid(os.getuid()).pw_name)
            self.assertIn(str(Path.home())+'::A,'+Plugin._get_user(), command)

    async def test_disable_reaps_only_owned_process(self):
        own = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)
        other = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        try:
            Plugin._proc = own
            await Plugin.set_enabled(Plugin(), False)
            self.assertIsNotNone(own.returncode)
            self.assertIsNone(other.poll())
            self.assertIsNone(Plugin._proc)
        finally:
            for process in (own, other):
                if process.poll() is None: process.terminate()
                process.wait(timeout=5)

    async def test_reaps_an_already_exited_child(self):
        own = subprocess.Popen([sys.executable, '-c', 'pass'])
        own.wait(timeout=5)
        Plugin._proc = own
        Plugin._stop_process()
        self.assertIsNone(Plugin._proc)

    async def test_stop_escalates_only_after_owned_timeout(self):
        process = unittest.mock.Mock()
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired('private child', 2), 0]
        Plugin._proc = process
        process.pid = 424242
        with patch.object(module.os, 'killpg') as kill:
            Plugin._stop_process()
        self.assertEqual(kill.call_args_list, [unittest.mock.call(process.pid,module.signal.SIGTERM),
                                               unittest.mock.call(process.pid,module.signal.SIGKILL)])
        self.assertEqual(process.wait.call_args_list,
                         [unittest.mock.call(timeout=2), unittest.mock.call(timeout=1)])
        self.assertIsNone(Plugin._proc)

    async def test_child_environment_and_owned_temporary_files(self):
        with patch.dict(os.environ, {'LD_LIBRARY_PATH':'private-loader-libs','PYTHONHOME':'private-loader-home',
                                     'PYTHONPATH':'private-loader-modules'}):
            with patch.object(module.subprocess,'Popen') as spawn:
                Plugin._start_process()
                _, options = spawn.call_args
                self.assertTrue(options['start_new_session'])
                for key in ('LD_LIBRARY_PATH','PYTHONHOME','PYTHONPATH'):
                    self.assertNotIn(key,options['env'])
                self.assertEqual(options['env']['TMPDIR'],str(folder/'private-runtime/copyparty-tmp'))
        Plugin._proc = None

    async def test_repeated_main_has_one_runner_and_unload_cancels_it(self):
        plugin = Plugin()
        await Plugin._main(plugin)
        first = Plugin._runner_handle
        await Plugin._main(plugin)
        self.assertIs(Plugin._runner_handle, first)
        await Plugin._unload(plugin)
        self.assertTrue(first.cancelled())
        self.assertIsNone(Plugin._runner_handle)
        self.assertFalse(Plugin._enabled)
        self.assertIsNone(Plugin._password)
        with patch.object(Plugin, '_start_process') as spawn:
            Plugin._enabled = True
            Plugin.copyparty_runner()
            spawn.assert_not_called()
            self.assertIsNone(Plugin._runner_handle)

    async def test_non_boolean_enable_is_refused(self):
        for value in ('false', 1, None, []):
            with self.assertRaises(ValueError): await Plugin.set_enabled(Plugin(), value)
        self.assertFalse(Plugin._enabled)


if __name__ == '__main__':
    try: unittest.main()
    finally:
        module.std_out_file.close()
        module.std_err_file.close()
