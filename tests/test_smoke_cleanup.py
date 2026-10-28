"""Smoke cleanup against real local Linux processes, never a headset or SSH."""
import sandbox  # noqa: F401
import json
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

    def test_unreadable_cwd_does_not_abort_scan_or_hide_readable_argv(self):
        owned = self.start(self.home, str(self.title / 'fc-smoke-exe.exe'))
        other = self.start(self.home, 'wineserver')
        with mock.patch.object(stop_processes.os, 'readlink', side_effect=PermissionError):
            self.assertTrue(stop_processes.owned(owned.pid, [str(self.title)]))
            self.assertFalse(stop_processes.owned(other.pid, [str(self.title)]))
            result = stop_processes.stop(['fc_smoke_exe'], grace=0.2)
        self.assertIn(owned.pid, result['stopped_pids'])
        self.assertEqual(owned.wait(timeout=5), -signal.SIGTERM)
        self.assertIsNone(other.poll())


class Safety(unittest.TestCase):
    def test_locked_preflight_rejects_active_or_unknown_proximity_before_titles(self):
        for proximity in ([], [88.0625], [4.6875, 88.0625], [None]):
            with self.subTest(proximity=proximity), mock.patch.object(
                    frame_smoke, 'remote', return_value=mock.Mock(
                        returncode=0, stdout=json.dumps({
                            'activity': 3, 'proximity': proximity, 'battery': [72]}))):
                with self.assertRaisesRegex(RuntimeError, 'proximity is active or unknown'):
                    frame_smoke.preflight()
        with mock.patch.object(frame_smoke, 'remote', return_value=mock.Mock(
                returncode=0, stdout=json.dumps({
                    'activity': 3, 'proximity': [4.6875], 'battery': [72]}))):
            self.assertEqual(frame_smoke.preflight()['proximity'], [4.6875])

    def test_missing_x86_runtime_skips_launch_but_still_removes_title(self):
        smoke = frame_smoke.Smoke()
        gid = 'fc_smoke_x86_64'
        with mock.patch.object(frame_smoke.tiny_programs, 'write', return_value=Path('/tmp/tiny')), \
             mock.patch.object(frame_smoke.frame_titles, 'install', return_value={
                 'runtime': 'SteamLinuxRuntime_4'}), \
             mock.patch.object(frame_smoke.frame_titles, 'list_titles', side_effect=[
                 [{'id': gid}], []]), \
             mock.patch.object(frame_smoke.frame_titles, 'launch') as launch, \
             mock.patch.object(frame_smoke.frame_titles, 'remove') as remove, \
             mock.patch.object(frame_smoke, 'steam_log_lines', side_effect=[
                 [], [], [], ['Tool 4183110 Steam Linux Runtime 4.0 is found, but is not installed']]), \
             mock.patch.object(frame_smoke, 'ssh', return_value=''), \
             mock.patch.object(frame_smoke, 'stop_titles', return_value={'stopped_pids': []}):
            frame_smoke.title_cycle(smoke, 'x86_64', '/tmp')
        self.assertEqual([step['step'] for step in smoke.steps],
                         ['x86_64: install', 'x86_64: launch', 'x86_64: remove'])
        self.assertTrue(smoke.steps[0]['ok'])
        self.assertFalse(smoke.steps[1]['ok'])
        self.assertTrue(smoke.steps[1]['skipped'])
        self.assertEqual(smoke.steps[1]['detail']['outcome'], 'runtime missing')
        self.assertTrue(smoke.steps[2]['ok'])
        self.assertNotIn(gid, smoke.installed)
        launch.assert_called_once_with(gid)
        remove.assert_called_once_with(gid)

    def test_optional_runtime_skip_fails_gate_and_is_counted_in_saved_result(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / 'results'
            folder = Path(root) / 'titles'
            folder.mkdir()
            def cycle(smoke, kind, _folder):
                if kind == 'x86_64':
                    def missing():
                        raise frame_smoke.Skipped('optional runtime absent', {'outcome': 'runtime missing'})
                    smoke.step(f'{kind}: launch', missing)
                else:
                    smoke.step(f'{kind}: launch', lambda: {'outcome': 'running'})
            with mock.patch.object(frame_smoke, 'RESULTS', output), \
                 mock.patch.object(frame_smoke, 'os_release', return_value={
                     'BUILD_ID': 'fake', 'VERSION_ID': 'fake', 'VARIANT_ID': 'fake'}), \
                 mock.patch.object(frame_smoke, 'ssh', return_value='yes'), \
                 mock.patch.object(frame_smoke, 'cleanup', return_value={}), \
                 mock.patch.object(frame_smoke, 'properties', return_value={}), \
                 mock.patch.object(frame_smoke, 'status', return_value={}), \
                 mock.patch.object(frame_smoke, 'title_cycle', side_effect=cycle), \
                 mock.patch.object(frame_smoke.tempfile, 'mkdtemp', return_value=str(folder)):
                self.assertEqual(frame_smoke.run_smoke(mock.Mock(pair=False),
                                 {'activity': 3, 'proximity': [], 'battery': [100]}), 1)
            result = json.loads(next(output.glob('*-fake.json')).read_text())
            self.assertEqual((result['passed'], result['skipped'], result['failed']), (6, 1, 0))
            self.assertEqual(next(s for s in result['steps'] if s['step'] == 'x86_64: launch')
                             ['detail']['outcome'], 'runtime missing')

    def test_non_test_ids_rejected_before_scanning(self):
        for ids in ([], ['portal2'], ['fc_smoke_exe/../portal2'], ['fc_smoke_custom']):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                stop_processes.stop(ids)

    @unittest.skipUnless(sys.platform == 'linux', 'Linux signalling helper')
    def test_lost_ownership_after_open_never_signalled(self):
        with mock.patch.object(stop_processes, 'candidates', side_effect=[[123], [], []]), \
                mock.patch.object(stop_processes.os, 'pidfd_open', return_value=9, create=True), \
                mock.patch.object(stop_processes.os, 'close'), \
                mock.patch.object(stop_processes, 'owned', return_value=False), \
                mock.patch.object(stop_processes.signal, 'pidfd_send_signal', create=True) as send:
            self.assertEqual(stop_processes.stop(['fc_smoke_exe'], grace=0), {'stopped_pids': []})
            send.assert_not_called()

    @unittest.skipUnless(sys.platform == 'linux', 'Linux signalling helper')
    def test_survivor_is_a_failure(self):
        with mock.patch.object(stop_processes, 'candidates', return_value=[123]), \
                mock.patch.object(stop_processes.os, 'pidfd_open', return_value=9, create=True), \
                mock.patch.object(stop_processes.os, 'close'), \
                mock.patch.object(stop_processes, 'owned', return_value=True), \
                mock.patch.object(stop_processes.signal, 'pidfd_send_signal', create=True):
            with self.assertRaisesRegex(RuntimeError, 'survived cleanup'):
                stop_processes.stop(['fc_smoke_exe'], grace=0)

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
            self.assertEqual(frame_smoke.run_smoke(mock.Mock(pair=False),
                             {'activity':3,'proximity':[],'battery':[100]}), 1)
            cycle.assert_not_called()
            self.assertEqual(len(list(Path(folder).glob('*-fake.json'))), 1)


class SharedSmokeLock(unittest.TestCase):
    def test_busy_lock_prevents_any_status_read_or_title_change(self):
        with mock.patch.object(frame_smoke.sys, 'argv', ['frame_smoke.py']), \
             mock.patch.object(frame_smoke, 'acquire_lock', return_value=False), \
             mock.patch.object(frame_smoke, 'preflight') as preflight, \
             mock.patch.object(frame_smoke, 'run_smoke') as run, \
             mock.patch.object(frame_smoke, 'release_lock') as release:
            self.assertEqual(frame_smoke.main(), 2)
            preflight.assert_not_called()
            run.assert_not_called()
            release.assert_not_called()

    def test_preflight_requires_standby_and_sufficient_battery(self):
        for state in ({'activity':1,'proximity':[1],'battery':[100]},
                      {'activity':None,'proximity':[],'battery':[100]},
                      {'activity':3,'proximity':[],'battery':[19]},
                      {'activity':3,'proximity':[],'battery':[]}):
            with self.subTest(state=state), mock.patch.object(frame_smoke, 'remote',
                    return_value=mock.Mock(returncode=0, stdout=json.dumps(state))):
                with self.assertRaises(RuntimeError):
                    frame_smoke.preflight()
        with mock.patch.object(frame_smoke, 'remote', return_value=mock.Mock(
                returncode=0, stdout=json.dumps({'activity':3,'proximity':[0],'battery':[99]}))):
            self.assertEqual(frame_smoke.preflight()['battery'], [99])

    def test_owner_checked_on_release_and_preflight_failure_still_releases(self):
        commands = []
        def remote(command, **_):
            commands.append(command)
            return mock.Mock(returncode=0)
        with mock.patch.object(frame_smoke, 'remote', side_effect=remote):
            self.assertTrue(frame_smoke.acquire_lock('frame-smoke-test-token'))
            self.assertTrue(frame_smoke.release_lock('frame-smoke-test-token'))
        self.assertIn('mkdir /tmp/frame-test.lock', commands[0])
        self.assertIn('> /tmp/frame-test.lock/owner', commands[0])
        self.assertIn('test "$(cat /tmp/frame-test.lock/owner)" = frame-smoke-test-token', commands[1])
        self.assertLess(commands[1].index('test '), commands[1].index('rm /tmp/frame-test.lock/owner'))

        with mock.patch.object(frame_smoke.sys, 'argv', ['frame_smoke.py']), \
             mock.patch.object(frame_smoke, 'acquire_lock', return_value=True), \
             mock.patch.object(frame_smoke, 'preflight', side_effect=RuntimeError('awake')), \
             mock.patch.object(frame_smoke, 'run_smoke') as run, \
             mock.patch.object(frame_smoke, 'release_lock', return_value=True) as release:
            self.assertEqual(frame_smoke.main(), 2)
            run.assert_not_called()
            release.assert_called_once()
            self.assertTrue(release.call_args.args[0].startswith('frame-smoke-'))


@unittest.skipUnless(os.name == 'posix', 'local POSIX shell required')
class OrphanCleanup(unittest.TestCase):
    """Run the real cleanup shell commands in a throwaway home; mock Steam/SSH."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.games = self.home / 'devkit-game'
        self.games.mkdir()
        self.shortcuts = set()
        self.sync_outputs = None
        self.events = []
        self.smoke = frame_smoke.Smoke()
        for target, name, kwargs in (
                (frame_smoke, 'ssh', {'side_effect': self.local_ssh}),
                (frame_smoke, 'stop_titles', {'side_effect': self.stop}),
                (frame_smoke.frame_titles, 'list_titles', {'return_value': []}),
                (frame_smoke.frame_titles, 'remove', {'side_effect': self.remove}),
                (frame_smoke.frame_titles, 'ensure_utils', {}),
                (frame_smoke.frame_titles, 'devkit_script', {'return_value': 'smoke-sync'})):
            patcher = mock.patch.object(target, name, **kwargs)
            setattr(self, name + '_mock', patcher.start())
            self.addCleanup(patcher.stop)

    def stop(self, ids):
        self.assertEqual(ids, stop_processes.IDS)
        self.events.append('stop')
        return {'stopped_pids': [42] if len(self.events) == 1 else []}

    def remove(self, gid):
        self.assertIn(gid, stop_processes.IDS)
        self.events.append('remove')
        shutil.rmtree(self.games / gid)

    def local_ssh(self, command, timeout=60):
        self.events.append(command)
        self.assertEqual(self.events[0], 'stop', 'processes must stop before file cleanup')
        if command == 'smoke-sync 2>&1':
            if self.sync_outputs is not None:
                return self.sync_outputs.pop(0)
            # Valve logs the registered IDs before reconciling with disk.
            out = '\n'.join(f'Found Devkit Game registered with Steam Client: {gid!r}'
                            for gid in sorted(self.shortcuts))
            self.shortcuts = {gid for gid in self.shortcuts if (self.games / gid).is_dir()}
            return out
        return subprocess.run(command, shell=True, check=True, capture_output=True,
                              text=True, timeout=timeout,
                              env={**os.environ, 'HOME': str(self.home)}).stdout

    def metadata(self, gid):
        paths = [self.games / f'{gid}-{kind}.json'
                 for kind in ('argv', 'env', 'settings', 'framecontrol')]
        for path in paths:
            path.write_text('{}')
        return paths

    def test_orphan_metadata_for_every_reserved_id_is_removed_and_shortcuts_rechecked(self):
        paths = [path for gid in stop_processes.IDS for path in self.metadata(gid)]
        self.shortcuts = set(stop_processes.IDS)
        result = frame_smoke.cleanup(self.smoke)
        self.assertTrue(all(not path.exists() for path in paths))
        self.assertFalse(self.shortcuts)
        self.assertEqual(result['removed'], sorted(stop_processes.IDS))
        self.assertEqual(result['process_cleanup'], [{'stopped_pids': [42]}, {'stopped_pids': []}])
        self.assertEqual(self.events[-1], 'stop')
        self.assertEqual(self.events.count('smoke-sync 2>&1'), 2)
        self.ensure_utils_mock.assert_called_once_with()
        self.remove_mock.assert_not_called()

    def test_shortcut_only_leftover_is_synced_without_title_or_install_record(self):
        self.shortcuts = {'fc_smoke_exe'}
        frame_smoke.cleanup(self.smoke)
        self.assertFalse(self.shortcuts)
        self.assertEqual(self.events.count('smoke-sync 2>&1'), 2)

    def test_unrelated_titles_and_metadata_survive_even_if_in_install_tracker(self):
        others = ('portal2', 'fc_smoke_custom', 'fc_smoke_exe-other', 'fc_smoke_exe_other')
        paths = []
        for gid in ('fc_smoke_exe', *others):
            (self.games / gid).mkdir()
            paths.extend(self.metadata(gid) if gid in others else [])
        self.shortcuts = {'fc_smoke_exe', *others}
        self.smoke.installed = {'fc_smoke_exe', *others, 'fc_smoke_exe/../portal2'}
        frame_smoke.cleanup(self.smoke)
        self.assertFalse((self.games / 'fc_smoke_exe').exists())
        self.assertTrue(all((self.games / gid).is_dir() for gid in others))
        self.assertTrue(all(path.exists() for path in paths))
        self.assertEqual(self.shortcuts, set(others))
        self.assertNotIn('fc_smoke_exe', self.smoke.installed)
        self.remove_mock.assert_called_once_with('fc_smoke_exe')

    def test_still_registered_current_or_legacy_shortcut_fails_cleanup(self):
        for gid in sorted(stop_processes.IDS):
            with self.subTest(gid=gid):
                self.sync_outputs = ['', f'Found Devkit Game registered with Steam Client: {gid!r}']
                self.smoke.installed = {gid}
                with self.assertRaisesRegex(AssertionError, f'{gid} is still registered with Steam'):
                    frame_smoke.cleanup(self.smoke)
                self.assertIn(gid, self.smoke.installed)

    def test_sync_failure_in_either_pass_fails_cleanup(self):
        for failed_pass in (0, 1):
            with self.subTest(failed_pass=failed_pass):
                self.sync_outputs = ['', '']
                self.sync_outputs[failed_pass] = 'Steam client sync of devkit games failed: offline'
                self.smoke.installed = {'fc_smoke_exe'}
                with self.assertRaisesRegex(AssertionError, 'sync of devkit games failed'):
                    frame_smoke.cleanup(self.smoke)
                self.assertIn('fc_smoke_exe', self.smoke.installed)

    def test_metadata_remaining_after_delete_fails_cleanup(self):
        self.metadata('fc_smoke_exe')
        real_ssh = self.local_ssh
        with mock.patch.object(frame_smoke, 'ssh', side_effect=lambda command, **kwargs:
                               '' if command.startswith('rm -f ') else real_ssh(command, **kwargs)):
            with self.assertRaisesRegex(AssertionError, 'fc_smoke_exe is still on the Frame'):
                frame_smoke.cleanup(self.smoke)

    def test_missing_utils_cannot_report_success_without_shortcut_verification(self):
        self.ensure_utils_mock.side_effect = frame_smoke.frame_android.FrameError('copy failed')
        with self.assertRaisesRegex(AssertionError, "syncing Steam's shortcuts: copy failed"):
            frame_smoke.cleanup(self.smoke)
        self.assertEqual(self.events[-1], 'stop')


@unittest.skipUnless(os.name == 'posix', 'POSIX wrapper')
class PortableWrapper(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='smoke wrapper ')
        self.addCleanup(self.tmp.cleanup)
        # macOS aliases /var to /private/var; relative commands need the physical cwd.
        self.folder = Path(self.tmp.name).resolve()
        self.bin = self.folder / 'bin'
        self.bin.mkdir()
        # No zsh or SSH on PATH: --help must exit before any headset access.
        (self.bin / 'dirname').symlink_to(shutil.which('dirname'))
        self.env = {**os.environ, 'PATH': str(self.bin), 'CDPATH': str(self.folder)}
        self.wrapper = SMOKE.parent.parent / 'scripts' / 'frame-smoke.sh'

    def test_help_runs_directly_and_with_posix_sh_from_another_cwd_without_zsh(self):
        (self.bin / 'python3').symlink_to(sys.executable)
        for launcher in ([], ['/bin/sh']):
            with self.subTest(launcher=launcher):
                result = subprocess.run([*launcher, str(self.wrapper), '--help'], cwd=self.folder,
                                        env=self.env, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('--pair', result.stdout)
                self.assertIn('Headset smoke test', result.stdout)

    def test_relative_invocation_preserves_arguments_and_python_exit_status(self):
        python = self.bin / 'python3'
        python.write_text('#!/bin/sh\nprintf "<%s>\\n" "$@"\nexit 7\n')
        python.chmod(0o755)
        result = subprocess.run([os.path.relpath(self.wrapper, self.folder), '--pair', 'two words', ''],
                                cwd=self.folder, env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual(result.stdout.splitlines(),
                         [f'<{SMOKE / "frame_smoke.py"}>', '<--pair>', '<two words>', '<>'])
