"""Smoke cleanup against real local Linux processes, never a headset or SSH."""
import sandbox  # noqa: F401
import os
from pathlib import Path
import shutil
import shlex
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SMOKE = Path(__file__).resolve().parent / 'smoke'
sys.path.insert(0, str(SMOKE))
import stop_processes  # noqa: E402
import frame_smoke  # noqa: E402


@unittest.skipUnless(sys.platform == 'linux' and hasattr(os, 'pidfd_open'), 'Linux pidfds required')
class RealProcesses(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.title = self.home / 'devkit-game' / 'fc_smoke_exe'
        self.title.mkdir(parents=True)
        self.children = []
        self.patcher = mock.patch.object(stop_processes.Path, 'home', return_value=self.home)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.addCleanup(self.reap)

    def reap(self):
        for child in self.children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)

    def start(self, cwd, *args, ignore=False):
        code = ('import signal,time; '
                + ('signal.signal(signal.SIGTERM, signal.SIG_IGN); ' if ignore else '')
                + 'print("ready", flush=True); time.sleep(60)')
        child = subprocess.Popen([sys.executable, '-c', code, *args], cwd=cwd,
                                 stdout=subprocess.PIPE, text=True)
        self.children.append(child)
        self.addCleanup(child.stdout.close)
        self.assertEqual(child.stdout.readline().strip(), 'ready')
        return child

    def test_deleted_title_process_is_stopped_but_similar_names_survive(self):
        owned = self.start(self.title)
        neighbour = self.title.with_name('fc_smoke_exe_other')
        neighbour.mkdir()
        other = self.start(neighbour, 'fc_smoke_exe', 'wine', 'proton')
        shutil.rmtree(self.title)
        # Reproduces the old success condition: no title remains, yet it runs.
        self.assertFalse(self.title.exists())
        self.assertIsNone(owned.poll())
        def local_target(command, *, input, timeout):
            return subprocess.run(shlex.split(command), input=input, text=True,
                                  capture_output=True, check=True, timeout=timeout,
                                  env={**os.environ, 'HOME': str(self.home)}).stdout

        # Exercise the production SSH command and stdin payload against a local
        # fake target, including the helper's CLI and JSON result contract.
        with mock.patch.object(frame_smoke.frame_android, 'ssh', side_effect=local_target):
            result = frame_smoke.stop_titles({'fc_smoke_exe'})
        self.assertIn(owned.pid, result['stopped_pids'])
        self.assertEqual(owned.wait(timeout=5), -signal.SIGTERM)
        self.assertIsNone(other.poll())

    def test_proton_style_absolute_argument_escalates_without_stopping_shared_wine(self):
        owned = self.start(self.home, str(self.title / 'fc-smoke-exe.exe'), ignore=True)
        shared = self.start(self.home, 'wineserver', '-p')
        quoted = self.start(self.home, 'echo ' + str(self.title / 'fc-smoke-exe.exe'))
        result = stop_processes.stop(['fc_smoke_exe'], grace=0.2)
        self.assertIn(owned.pid, result['stopped_pids'])
        self.assertEqual(owned.wait(timeout=5), -signal.SIGKILL)
        self.assertIsNone(shared.poll())
        self.assertIsNone(quoted.poll())
        self.assertEqual(stop_processes.stop(['fc_smoke_exe']), {'stopped_pids': []})


class Safety(unittest.TestCase):
    def test_non_test_ids_rejected_before_scanning(self):
        for ids in ([], ['portal2'], ['fc_smoke_exe/../portal2'], ['fc_smoke_custom']):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                stop_processes.stop(ids)

    def test_lost_ownership_after_open_never_signalled(self):
        with mock.patch.object(stop_processes, 'candidates', side_effect=[[123], [], []]), \
                mock.patch.object(stop_processes.os, 'pidfd_open', return_value=9, create=True), \
                mock.patch.object(stop_processes.os, 'close'), \
                mock.patch.object(stop_processes, 'owned', return_value=False), \
                mock.patch.object(stop_processes.signal, 'pidfd_send_signal', create=True) as send:
            self.assertEqual(stop_processes.stop(['fc_smoke_exe'], grace=0), {'stopped_pids': []})
            send.assert_not_called()

    def test_survivor_is_a_failure(self):
        with mock.patch.object(stop_processes, 'candidates', return_value=[123]), \
                mock.patch.object(stop_processes.os, 'pidfd_open', return_value=9, create=True), \
                mock.patch.object(stop_processes.os, 'close'), \
                mock.patch.object(stop_processes, 'owned', return_value=True), \
                mock.patch.object(stop_processes.signal, 'pidfd_send_signal', create=True):
            with self.assertRaisesRegex(RuntimeError, 'survived cleanup'):
                stop_processes.stop(['fc_smoke_exe'], grace=0)

    def test_cleanup_scans_even_when_title_already_removed(self):
        with mock.patch.object(frame_smoke.frame_titles, 'list_titles', return_value=[]), \
                mock.patch.object(frame_smoke, 'ssh') as ssh, \
                mock.patch.object(frame_smoke, 'stop_titles', return_value={'stopped_pids': [42]}) as stop:
            result = frame_smoke.cleanup(frame_smoke.Smoke())
            self.assertEqual(stop.call_args_list, [mock.call(stop_processes.IDS)] * 2)
            self.assertEqual(result['process_cleanup'][0]['stopped_pids'], [42])
            ssh.assert_not_called()

    def test_stop_failure_prevents_file_removal(self):
        with mock.patch.object(frame_smoke.frame_titles, 'list_titles', return_value=[{'id': 'fc_smoke_exe'}]), \
                mock.patch.object(frame_smoke, 'ssh') as ssh, \
                mock.patch.object(frame_smoke, 'stop_titles', side_effect=RuntimeError('still running')):
            with self.assertRaisesRegex(RuntimeError, 'still running'):
                frame_smoke.cleanup(frame_smoke.Smoke())
            ssh.assert_not_called()

    def test_failed_initial_cleanup_prevents_install_and_records_failure(self):
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(frame_smoke, 'RESULTS', Path(folder)), \
                mock.patch.object(frame_smoke.sys, 'argv', ['frame_smoke.py']), \
                mock.patch.object(frame_smoke.subprocess, 'run', return_value=mock.Mock(returncode=0)), \
                mock.patch.object(frame_smoke.tempfile, 'mkdtemp', return_value=folder), \
                mock.patch.object(frame_smoke, 'os_release', return_value={
                    'BUILD_ID': 'fake', 'VERSION_ID': 'fake', 'VARIANT_ID': 'fake'}), \
                mock.patch.object(frame_smoke, 'ssh', return_value='yes'), \
                mock.patch.object(frame_smoke, 'cleanup', side_effect=RuntimeError('cannot stop')), \
                mock.patch.object(frame_smoke, 'title_cycle') as cycle, \
                mock.patch('builtins.print'):
            self.assertEqual(frame_smoke.main(), 1)
            cycle.assert_not_called()
            self.assertEqual(len(list(Path(folder).glob('*-fake.json'))), 1)
