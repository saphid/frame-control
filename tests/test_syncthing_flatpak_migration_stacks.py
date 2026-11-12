"""Bound guest-root sampling to the real migration service, never host PIDs."""

import copy
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class MigrationStacks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.observer = load('migration_stacks', 'tests/decky-runtime/syncthing_migration_stacks.py')
        cls.package = load('migration_package', 'scripts/framey-test-syncthing-flatpak-package.py')

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.folder = Path(directory.name)
        self.proc = self.folder / 'proc'
        self.cgroups = self.folder / 'cgroups'
        group = self.cgroups / self.observer.GROUP.lstrip('/')
        group.mkdir(parents=True)
        self.pid_file = group / 'cgroup.procs'
        self.pid_file.write_text('41\n42\n')
        self.process(41)
        self.process(42)
        self.properties = dict(MainPID='41', ControlGroup=self.observer.GROUP,
                               TimeoutStopUSec='1min 30s', ActiveState='active', PythonReady=True)

    def process(self, pid, *, uid='1100', group=None, start=123):
        base = self.proc / str(pid)
        base.mkdir(parents=True, exist_ok=True)
        fields = ['S', '40'] + ['0'] * 17 + [str(start)]
        (base / 'stat').write_text(str(pid) + ' (loader ) child) ' + ' '.join(fields))
        (base / 'status').write_text('Uid:\t' + '\t'.join([uid] * 4) + '\n')
        (base / 'cgroup').write_text('0::' + (group or self.observer.GROUP) + '\n')

    def dump(self, *_):
        result = dict(returncode=0, timedOut=False, outputTruncated=False,
                      stdout='Thread 1: _run_once (asyncio/base_events.py:1)\n', stderr='')
        for name in ('stdout', 'stderr'):
            result[name+'Sha256'] = hashlib.sha256(result[name].encode()).hexdigest()
        return result

    def sample(self, dump=None, **kwargs):
        return self.observer.sample_group(self.properties, Path('/unused/pinned-sampler'),
                                          proc=self.proc, cgroups=self.cgroups,
                                          dump=dump or self.dump, **kwargs)

    def report(self):
        metadata = {'executableSha256': 'a' * 64, 'architecture': 'x86_64'}
        return dict(sampler=metadata, unit=self.observer.UNIT, observerJoined=True,
                    deactivationTimeBasis='first observed deactivating state',
                    changesStopBudget=False, historicalCauseEstablished=False,
                    snapshots=[dict(window='baseline', activeState='active', pythonServerReady=True,
                                    **self.sample())])

    def test_identity_handles_parentheses_and_requires_all_uids(self):
        identity = self.observer.identity(41, proc=self.proc)
        self.assertEqual((identity['startTicks'], identity['parentPid']), (123, 40))
        (self.proc / '41/status').write_text('Uid:\t1100\t0\t1100\t1100\n')
        with self.assertRaises(ValueError):
            self.observer.identity(41, proc=self.proc)

    def test_foreign_cgroup_and_nonpositive_start_are_refused(self):
        for changed in ({'group': '/system.slice/unrelated.service'}, {'start': 0}):
            self.process(41, **changed)
            with self.assertRaises(ValueError):
                self.observer.identity(41, proc=self.proc)
        with self.assertRaises(ValueError):
            self.observer.identity(1, proc=self.proc)

    def test_sampling_retains_both_sides_of_verified_identity(self):
        snapshot = self.sample()
        self.assertEqual(len(snapshot['processes']), 2)
        self.assertTrue(all(p['identityUnchanged'] for p in snapshot['processes']))
        self.assertFalse(snapshot['processesTruncated'])

    def test_pid_reuse_uid_change_and_cgroup_escape_discard_unbound_text(self):
        for changed in ({'start': 124}, {'uid': '0'}, {'group': '/system.slice/other.service'}):
            with self.subTest(changed=changed):
                self.process(41)
                def dump(sampler, pid):
                    sample = self.dump()
                    if pid == 41:
                        self.process(pid, **changed)
                    return sample
                entry = self.sample(dump)['processes'][0]
                self.assertFalse(entry['identityUnchanged'])
                self.assertTrue(entry['sampleOutputDiscarded'])
                self.assertNotIn('stdout', entry)

    def test_exited_process_is_reported_without_stopping_other_samples(self):
        def dump(sampler, pid):
            if pid == 41:
                (self.proc / '41/stat').unlink()
            return self.dump()
        entries = self.sample(dump)['processes']
        self.assertIn('error', entries[0])
        self.assertTrue(entries[1]['identityUnchanged'])

    def test_foreign_group_changed_budget_and_missing_main_refuse_sampling(self):
        for change in ({'ControlGroup': '/other'}, {'TimeoutStopUSec': 'infinity'}, {'MainPID': '99'}):
            original = self.properties.copy()
            self.properties.update(change)
            dump = Mock()
            with self.assertRaises(ValueError):
                self.sample(dump)
            dump.assert_not_called()
            self.properties = original

    def test_pid_count_is_bounded_and_cancellation_does_not_sample(self):
        for pid in range(43, 52):
            self.process(pid)
        self.pid_file.write_text('\n'.join(map(str, range(41, 52))))
        snapshot = self.sample()
        self.assertTrue(snapshot['processesTruncated'])
        self.assertEqual(len(snapshot['processes']), 8)
        dump = Mock()
        snapshot = self.sample(dump, cancelled=lambda: True)
        self.assertTrue(snapshot['cancelled'])
        dump.assert_not_called()

    def test_unsupported_bootloader_is_not_python_evidence(self):
        def unsupported(*_):
            value = self.dump()
            value.update(returncode=1, stdout='', stderr='Failed to find a python interpreter')
            for name in ('stdout', 'stderr'):
                value[name+'Sha256'] = hashlib.sha256(value[name].encode()).hexdigest()
            return value
        report = self.report()
        report['snapshots'][0].update(self.sample(unsupported))
        with self.assertRaisesRegex(ValueError, 'No identity-bound'):
            self.package.verify_migration_stacks(report, report['sampler'])

    def test_baseline_and_stop_windows_run_once_without_controlling_service(self):
        captures = Mock(return_value={})
        observer = self.observer.Observer(Path('/unused'), {}, [], capture=captures)
        observer.tick(self.properties, 1)
        observer.tick(self.properties, 2)
        stopped = dict(self.properties, ActiveState='deactivating')
        for now in (3, 12, 13, 13, 33, 63, 80):
            observer.tick(stopped, now)
        self.assertEqual([s['window'] for s in observer.report['snapshots']], ['baseline', 10, 30, 60])
        self.assertEqual(captures.call_count, 4)
        self.assertFalse(observer.report['changesStopBudget'])

    def test_late_deactivating_service_is_not_a_running_baseline(self):
        capture = Mock()
        observer = self.observer.Observer(Path('/unused'), {}, [], capture=capture)
        observer.tick(dict(self.properties, ActiveState='deactivating'), 10)
        observer.tick(dict(self.properties, ActiveState='inactive'), 11)
        capture.assert_not_called()
        self.assertEqual(observer.report['snapshots'], [])

    def test_bootloader_active_state_does_not_replace_python_readiness(self):
        capture = Mock(return_value={})
        observer = self.observer.Observer(Path('/unused'), {}, [], capture=capture)
        observer.tick(dict(self.properties, PythonReady=False), 1)
        capture.assert_not_called()
        observer.tick(self.properties, 2)
        capture.assert_called_once()

    def test_readiness_checks_status_without_reading_an_auth_token(self):
        properties = '\n'.join(k+'='+v for k, v in self.properties.items()
                               if k != 'PythonReady')
        response = Mock(status=200)
        connection = Mock()
        connection.getresponse.return_value = response
        observer = self.observer.Observer(Path('/unused'), {}, ['owned-user'])
        with patch.object(self.observer.subprocess, 'run', return_value=Mock(
                returncode=0, stdout=properties)), patch.object(
                self.observer.http.client, 'HTTPConnection', return_value=connection):
            self.assertTrue(observer.properties()['PythonReady'])
        connection.request.assert_called_once_with('HEAD', '/auth/token')
        response.read.assert_not_called()
        connection.close.assert_called_once()

    def test_sampler_payload_binds_loader_observer_and_pinned_sampler(self):
        sampler = Mock()
        sampler.sampler_bytes.return_value = (b'verified native executable', {
            'executableSha256': hashlib.sha256(b'verified native executable').hexdigest()})
        with patch.object(self.package, 'module', return_value=sampler):
            payloads, metadata = self.package.migration_stack_payloads(
                Path('/cached-wheel'), 'aarch64', 'c' * 64)
        sampler.sampler_bytes.assert_called_once_with(Path('/cached-wheel'), 'aarch64')
        self.assertEqual(payloads['migration-py-spy'], b'verified native executable')
        self.assertEqual(metadata['loaderSha256'], 'c' * 64)
        self.assertEqual(metadata['observerSha256'], hashlib.sha256(
            payloads['syncthing_migration_stacks.py']).hexdigest())
        self.assertEqual(metadata['architecture'], 'aarch64')

    def test_cli_refuses_invalid_diagnostic_modes_before_touching_inputs(self):
        required = ['probe', '--rootfs-tar', '/unused', '--bundles', '/unused',
                    '--key', '/unused', '--output', '/unused']
        for flags in (['--migration-stacks'],
                      ['--migration-stacks', '--candidate-helper', '/unused', '--browser-setup'],
                      ['--migration-sampler-wheel', '/unused']):
            with self.subTest(flags=flags), patch.object(sys, 'argv', required+flags), \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                self.package.main()
            self.assertEqual(error.exception.code, 2)

    def test_observer_is_joined_after_user_probe_failure(self):
        queried = threading.Event()
        def query():
            queried.set()
            return {}
        observer = self.observer.Observer(Path('/unused'), {}, [], query=query)
        with self.assertRaisesRegex(RuntimeError, 'user probe'):
            with observer:
                self.assertTrue(queried.wait(timeout=2))
                raise RuntimeError('user probe')
        self.assertTrue(observer.report['observerJoined'])
        self.assertFalse(observer.thread.is_alive())

    def test_valid_fixture_proof_is_not_a_historical_cause_claim(self):
        report = self.report()
        self.package.verify_migration_stacks(report, report['sampler'])
        self.assertFalse(report['historicalCauseEstablished'])

    def test_proof_rejects_missing_identity_tampered_stacks_and_incomplete_cleanup(self):
        original = self.report()
        changes = [lambda r: r.update(observerJoined=False),
                   lambda r: r.update(deactivationTimeBasis='exact stop invocation'),
                   lambda r: r.update(historicalCauseEstablished=True),
                   lambda r: r['snapshots'][0].update(activeState='deactivating'),
                   lambda r: r['snapshots'][0]['processes'][0].update(stdout='tampered'),
                   lambda r: r['snapshots'][0]['processes'][0]['identity'].update(uid=0),
                   lambda r: r['snapshots'][0]['processes'][0].update(identityUnchanged=False)]
        for change in changes:
            report = copy.deepcopy(original)
            change(report)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.package.verify_migration_stacks(report, original['sampler'])

    def test_timeout_and_truncated_samples_cannot_supply_required_baseline(self):
        for flag in ('timedOut', 'outputTruncated'):
            report = self.report()
            for process in report['snapshots'][0]['processes']:
                process[flag] = True
            with self.assertRaisesRegex(ValueError, 'No identity-bound'):
                self.package.verify_migration_stacks(report, report['sampler'])

    def test_cgroup_disappearance_during_stop_is_an_explicit_gap_without_stack_text(self):
        report = self.report()
        missing = dict(window=10, activeState='deactivating', observedDeactivationSeconds=10.1,
                       error='FileNotFoundError: migration cgroup disappeared')
        report['snapshots'].append(missing)
        self.package.verify_migration_stacks(report, report['sampler'])
        for name, value in (('stdout', 'unbound'), ('processes', [self.sample()['processes'][0]])):
            report['snapshots'][-1] = dict(missing, **{name: value})
            with self.assertRaises(ValueError):
                self.package.verify_migration_stacks(report, report['sampler'])

    def test_host_and_unprivileged_invocation_are_refused(self):
        with patch.object(self.observer.os, 'getuid', return_value=1100, create=True):
            with self.assertRaisesRegex(RuntimeError, 'private systemd guest'):
                self.observer.guest_observer({}, [])

    def test_guest_refuses_changed_sampler_loader_or_observer_before_install(self):
        values = {'migration-py-spy': b'sampler', 'PluginLoader': b'loader',
                  'syncthing_migration_stacks.py': b'observer'}
        metadata = dict(architecture='x86_64', **{
            key: hashlib.sha256(value).hexdigest() for key, value in
            [('executableSha256', b'sampler'), ('loaderSha256', b'loader'),
             ('observerSha256', b'observer')]})
        # Emulate either runner's path spelling without touching its filesystem.
        for flavour in (PurePosixPath, PureWindowsPath):
            for changed in values:
                def read_bytes(path):
                    return b'tampered' if path.name == changed else values[path.name]
                def read_text(path):
                    return ('Frame Control Flatpak VM v1\n' if path.name == 'framey-owned-vm'
                            else 'systemd\n')
                opened = Mock()
                guest_path = type('GuestPath', (flavour,), dict(
                    read_text=read_text, read_bytes=read_bytes, open=opened))
                with self.subTest(flavour=flavour.__name__, changed=changed), \
                        patch.object(self.observer.os, 'getuid', return_value=0, create=True), \
                        patch.object(self.observer.os, 'getpid', return_value=42), \
                        patch.object(self.observer.os, 'uname', return_value=Mock(machine='x86_64'), create=True), \
                        patch.object(self.observer, 'Path', guest_path), \
                        patch.object(self.observer, '__file__', '/repo/syncthing_migration_stacks.py'):
                    with self.assertRaisesRegex(ValueError, 'provenance mismatch'):
                        self.observer.guest_observer(metadata, [])
                    opened.assert_not_called()

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Guest sampler uses Linux pipes')
    def test_real_sampler_subprocess_has_hard_pipe_bounds_and_is_reaped(self):
        executable = self.folder / 'sampler'
        executable.write_text('#!' + sys.executable + '\nimport os\nos.write(2,b"e"*32768)\nos.write(1,b"x"*32768)\n')
        executable.chmod(0o700)
        result = self.observer.bounded_dump(executable, 41)
        self.assertTrue(result['outputTruncated'])
        self.assertLessEqual(len(result['stdout']), self.observer.OUTPUT_LIMITS[0])
        self.assertLessEqual(len(result['stderr']), self.observer.OUTPUT_LIMITS[1])
        self.assertIsInstance(result['returncode'], int)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Guest sampler uses Linux pipes')
    def test_real_sampler_timeout_is_bounded_and_reaped(self):
        executable = self.folder / 'sampler'
        executable.write_text('#!' + sys.executable + '\nimport time\ntime.sleep(30)\n')
        executable.chmod(0o700)
        with patch.object(self.observer, 'DUMP_SECONDS', 0.1):
            result = self.observer.bounded_dump(executable, 41)
        self.assertTrue(result['timedOut'])
        self.assertIsInstance(result['returncode'], int)


if __name__ == '__main__':
    unittest.main()
