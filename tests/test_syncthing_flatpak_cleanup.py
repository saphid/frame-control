"""Instance cleanup tolerates registry lag, but never ignores a live entry."""
import ast
from contextlib import ExitStack
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class InstanceCleanup(unittest.TestCase):
    def probe(self, listings, ticks):
        path = Path(__file__).resolve().parent/'decky-runtime/syncthing_flatpak_package.py'
        tree = ast.parse(path.read_text())
        tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in ('wait', 'wait_for_instances')]
        scope = dict(APP='me.kozec.syncthingtk', PROGRESS={},
                     flat=Mock(side_effect=listings),
                     time=SimpleNamespace(monotonic=Mock(side_effect=ticks), sleep=Mock()))
        exec(compile(tree, str(path), 'exec'), scope)
        return scope

    def test_reaped_process_may_leave_transient_registry_entry(self):
        app = 'me.kozec.syncthingtk'
        scope = self.probe([app, app+'\nother.app', 'other.app'], [0, 0, 0, 1, 2, 3])
        scope['wait_for_instances']()
        self.assertEqual(scope['flat'].call_count, 3)
        scope['flat'].assert_called_with('ps', '--columns=application', timeout=10)
        self.assertEqual(scope['PROGRESS']['remainingFlatpakApplications'], ['other.app'])
        self.assertEqual(scope['PROGRESS']['instanceCleanupElapsedSeconds'], 3)
        self.assertEqual(scope['time'].sleep.call_count, 2)

    def test_persistent_registry_entry_fails_with_last_listing_retained(self):
        scope = self.probe(['me.kozec.syncthingtk'], [0, 0, 0, 91])
        with self.assertRaisesRegex(RuntimeError, 'instance registry cleanup'):
            scope['wait_for_instances']()
        self.assertEqual(scope['PROGRESS']['remainingFlatpakApplications'], ['me.kozec.syncthingtk'])
        self.assertNotIn('instanceCleanupElapsedSeconds', scope['PROGRESS'])

    def test_failed_registry_query_is_not_credited_as_cleanup(self):
        scope = self.probe([RuntimeError('query failed')], [0, 0, 0])
        with self.assertRaisesRegex(RuntimeError, 'query failed'):
            scope['wait_for_instances']()
        self.assertEqual(scope['PROGRESS'], {})


class MigrationInstanceCleanup(unittest.TestCase):
    def probe(self, listings, ticks):
        root = Path(__file__).resolve().parent/'decky-runtime'
        migration = ast.parse((root/'syncthing_migration.py').read_text())
        service = ast.parse((root/'syncthing_service.py').read_text())
        functions = [node for tree, name in ((migration, 'wait_for_instances'), (service, 'wait'))
                     for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
        tree = ast.Module(body=functions, type_ignores=[])
        scope = dict(json=json, subprocess=SimpleNamespace(check_output=Mock(side_effect=listings)),
                     time=SimpleNamespace(monotonic=Mock(side_effect=ticks), sleep=Mock()),
                     WebSocketException=type('WebSocketException', (Exception,), {}))
        exec(compile(tree, str(root/'syncthing_migration.py'), 'exec'), scope)
        main = next(node for node in migration.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
        # Execute the actual final cleanup, after service/process teardown,
        # with intact private data and no owned unit/receipt. This reproduces
        # the CI failure with the original immediate registry assertion too.
        cleanup = compile(ast.Module(body=main.body[-5:], type_ignores=[]),
                          str(root/'syncthing_migration.py'), 'exec')
        scope.update(app='me.kozec.syncthingtk', retained={}, runtime=Path('/private-fixture'),
                     managed=SimpleNamespace(exists=lambda: False),
                     receipt=SimpleNamespace(exists=lambda: False), print=Mock())
        def run_cleanup(report):
            scope['report'] = report
            exec(cleanup, scope)
        scope['run_cleanup'] = run_cleanup
        return scope

    def test_migration_waits_for_registry_after_owned_service_stops(self):
        app = 'me.kozec.syncthingtk'
        scope = self.probe([app, app+'\nother.app', 'other.app'], [0, 0, 0, 1, 2, 3])
        report = {}
        scope['run_cleanup'](report)
        self.assertEqual(scope['subprocess'].check_output.call_count, 3)
        scope['subprocess'].check_output.assert_called_with(
            ['/usr/bin/flatpak', 'ps', '--columns=application'], text=True, timeout=10)
        self.assertEqual(report['remainingFlatpakApplications'], ['other.app'])
        self.assertEqual(report['instanceCleanupElapsedSeconds'], 3)
        self.assertEqual(scope['time'].sleep.call_count, 2)
        self.assertTrue(report['noOwnedFlatpakInstancesRemain'])

    def test_migration_persistent_instance_fails_with_last_listing(self):
        scope = self.probe(['me.kozec.syncthingtk'], [0, 0, 0, 61])
        report = {}
        with self.assertRaisesRegex(RuntimeError, "remaining applications=.*me.kozec.syncthingtk"):
            scope['run_cleanup'](report)
        self.assertEqual(report['remainingFlatpakApplications'], ['me.kozec.syncthingtk'])
        self.assertNotIn('instanceCleanupElapsedSeconds', report)
        self.assertNotIn('noOwnedFlatpakInstancesRemain', report)

    def test_migration_failed_query_is_not_cleanup_proof(self):
        error = RuntimeError('query failed')
        scope = self.probe([error], [0, 0, 0])
        report = {}
        with self.assertRaisesRegex(RuntimeError, 'query failed'):
            scope['run_cleanup'](report)
        self.assertEqual(report, {})

    def test_migration_allows_a_different_application_with_similar_name(self):
        scope = self.probe(['me.kozec.syncthingtk.other'], [0, 0, 0, 1])
        report = {}
        scope['run_cleanup'](report)
        self.assertEqual(report['remainingFlatpakApplications'], ['me.kozec.syncthingtk.other'])


class DeckyShutdownLog(unittest.TestCase):
    def check_log(self, text):
        path = Path(__file__).resolve().parent/'decky-runtime/syncthing_service.py'
        function = next(node for node in ast.parse(path.read_text()).body
                        if isinstance(node, ast.FunctionDef) and node.name == 'verify_decky_log')
        scope = {'print': Mock()}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), scope)
        return scope['verify_decky_log'](io.StringIO(text))

    def test_actual_migration_shutdown_cancellation_is_not_clean(self):
        # Retained from exact-head CI artifact 13002674726. Its unit/package
        # summary passed, but Decky's migration loader logged this failure.
        text = ('[main][INFO]: Error during shutdown:\n'
                '  File "decky_loader/plugin/plugin.py", line 183, in kill_if_still_running\n'
                '  File "asyncio/tasks.py", line 712, in sleep\n'
                'asyncio.exceptions.CancelledError\n'
                '[main][INFO]: Cancelling tasks...\n[main][INFO]: Shutdown finished.\n')
        with self.assertRaisesRegex(AssertionError, 'Decky shutdown errors'):
            self.check_log(text)

    def test_normal_shutdown_task_cleanup_is_allowed(self):
        self.check_log('[main][INFO]: Cancelling tasks...\n[main][INFO]: Shutdown finished.\n')


class MigrationFailedStopCleanup(unittest.TestCase):
    def probe(self, stop_error=None, log_error=None):
        root = Path(__file__).resolve().parent/'decky-runtime'
        main = next(node for node in ast.parse((root/'syncthing_migration.py').read_text()).body
                    if isinstance(node, ast.FunctionDef) and node.name == 'main')
        final = next(node for node in main.body if isinstance(node, ast.Try)).finalbody
        log = io.StringIO('last loader phase before the stop failure\n')
        emitted = []
        def check_log(stream):
            stream.seek(0)
            emitted.append(stream.read())
            if log_error:
                raise log_error
        scope = dict(ExitStack=ExitStack, report={}, helper_pid=811,
                     decky_unit=SimpleNamespace(name='owned-decky', unlink=Mock()),
                     unit=SimpleNamespace(name='owned-legacy', exists=lambda: True,
                                          read_bytes=lambda: b'owned fixture', unlink=Mock()),
                     unit_bytes=b'owned fixture', ctl=Mock(), prop=Mock(return_value='0'),
                     stop_decky_service=Mock(side_effect=stop_error),
                     unrelated=SimpleNamespace(poll=Mock(return_value=None),
                                               terminate=Mock(), wait=Mock()),
                     wait=Mock(), Path=Mock(), logs=[log], verify_decky_log=check_log)
        def finish():
            exec(compile(ast.Module(body=final, type_ignores=[]), str(root/'syncthing_migration.py'),
                         'exec'), scope)
        return scope, finish, log, emitted

    def test_forced_stop_still_reaps_fixtures_and_emits_loader_log(self):
        error = AssertionError('systemd Result=timeout; ExecMainStatus=9')
        scope, finish, log, emitted = self.probe(stop_error=error)
        with self.assertRaises(AssertionError) as raised:
            finish()
        self.assertIs(raised.exception, error)
        scope['wait'].assert_called_once()
        scope['unrelated'].terminate.assert_called_once()
        scope['unrelated'].wait.assert_called_once_with(timeout=5)
        scope['ctl'].assert_any_call('stop', 'owned-legacy')
        scope['unit'].unlink.assert_called_once()
        self.assertEqual(emitted, ['last loader phase before the stop failure\n'])
        self.assertTrue(log.closed)
        self.assertNotIn('ownedMigrationDeckyServiceRemoved', scope['report'])
        self.assertNotIn('ownedProcessesReaped', scope['report'])

    def test_log_failure_retains_stop_failure_and_closes_log(self):
        error = AssertionError('systemd Result=timeout')
        bad_log = AssertionError('Decky shutdown errors')
        scope, finish, log, emitted = self.probe(stop_error=error, log_error=bad_log)
        with self.assertRaises(AssertionError) as raised:
            finish()
        self.assertIs(raised.exception, bad_log)
        self.assertIs(raised.exception.__context__, error)
        scope['unrelated'].wait.assert_called_once_with(timeout=5)
        self.assertTrue(emitted)
        self.assertTrue(log.closed)
        self.assertNotIn('deckyShutdownLogChecked', scope['report'])

    def test_successful_stop_keeps_strict_cleanup_evidence(self):
        scope, finish, log, emitted = self.probe()
        finish()
        scope['stop_decky_service'].assert_called_once_with('owned-decky', scope['report'], [log])
        scope['decky_unit'].unlink.assert_called_once()
        scope['unit'].unlink.assert_called_once()
        scope['unrelated'].wait.assert_called_once_with(timeout=5)
        self.assertTrue(scope['report']['ownedMigrationDeckyServiceRemoved'])
        self.assertTrue(scope['report']['deckyShutdownLogChecked'])
        self.assertTrue(log.closed)
        self.assertTrue(emitted)


class OwnedDeckyStop(unittest.TestCase):
    def probe(self, properties, ticks):
        path = Path(__file__).resolve().parent/'decky-runtime/syncthing_service.py'
        module = ast.parse(path.read_text())
        functions = [node for node in module.body if isinstance(node, ast.FunctionDef)
                     and node.name in ('wait', 'stop_decky_service')]
        scope = dict(json=json, prop=Mock(side_effect=properties), ctl=Mock(), print=Mock(),
                     decky_stop_snapshot=Mock(side_effect=lambda unit, logs: {'unit': unit}),
                     Path=Mock(return_value=SimpleNamespace(exists=lambda: False)),
                     time=SimpleNamespace(monotonic=Mock(side_effect=ticks), sleep=Mock()),
                     WebSocketException=type('WebSocketException', (Exception,), {}))
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), scope)
        return scope

    def test_manager_completion_after_command_budget_still_requires_clean_result(self):
        scope = self.probe(['811', '1min 30s', 'mixed', 'deactivating', 'inactive', 'success', '0', '1', '0'],
                           [0, 0, 0, 1, 40, 41])
        report = {}
        scope['stop_decky_service']('frame-control-decky.service', report)
        scope['ctl'].assert_called_once_with('stop', '--no-block', 'frame-control-decky.service')
        scope['Path'].assert_called_once_with('/proc/811')
        self.assertEqual(report['ownedDeckyStop']['result'], 'success')
        self.assertEqual(report['ownedDeckyStop']['elapsedSeconds'], 41)

    def test_systemd_forced_timeout_is_not_successful_cleanup(self):
        scope = self.probe(['811', '1min 30s', 'mixed', 'failed', 'timeout', '0', '2', '9'], [0, 0, 0, 91])
        report = {}
        with self.assertRaises(AssertionError):
            scope['stop_decky_service']('frame-control-decky.service', report)
        self.assertEqual(report['ownedDeckyStop']['result'], 'timeout')
        self.assertEqual(report['ownedDeckyStop']['elapsedSeconds'], 91)
        scope['print'].assert_called_once()

    def test_loader_exit_error_is_not_successful_cleanup(self):
        scope = self.probe(['811', '1min 30s', 'mixed', 'failed', 'exit-code', '0', '1', '1'],
                           [0, 0, 0, 2])
        report = {}
        with self.assertRaises(AssertionError):
            scope['stop_decky_service']('frame-control-decky.service', report)
        self.assertEqual(report['ownedDeckyStop']['result'], 'exit-code')
        self.assertEqual(report['ownedDeckyStop']['execMainStatus'], '1')
        scope['print'].assert_called_once()

    def test_persistent_stop_job_fails_and_retains_last_state(self):
        scope = self.probe(['811', '1min 30s', 'mixed', 'deactivating'], [0, 0, 0, 1, 101, 102])
        report = {}
        with self.assertRaisesRegex(RuntimeError, 'owned Decky service stop'):
            scope['stop_decky_service']('frame-control-decky.service', report)
        self.assertEqual(report['ownedDeckyStop']['activeState'], 'deactivating')
        self.assertNotIn('result', report['ownedDeckyStop'])
        scope['print'].assert_called_once()

    def test_slow_stop_retains_three_snapshots_before_forced_kill_and_still_fails(self):
        scope = self.probe(['811', '1min 30s', 'mixed', *(['deactivating'] * 4),
                            'failed', 'timeout', '0', '2', '9'],
                           [0, 0, 0, 11, 20, 31, 40, 61, 70, 81, 82, 91])
        report, logs = {}, [object()]
        with self.assertRaises(AssertionError):
            scope['stop_decky_service']('frame-control-decky.service', report, logs)
        self.assertEqual([s['elapsedSeconds'] for s in report['ownedDeckyStop']['slowStopDiagnostics']],
                         [11, 31, 61])
        self.assertEqual(scope['decky_stop_snapshot'].call_count, 4)
        scope['decky_stop_snapshot'].assert_called_with('frame-control-decky.service', logs)
        scope['ctl'].assert_called_once_with('stop', '--no-block', 'frame-control-decky.service')
        self.assertEqual(report['ownedDeckyStop']['result'], 'timeout')
        self.assertEqual(scope['print'].call_count, 4)

    def test_diagnostic_read_failure_does_not_mask_manager_failure(self):
        scope = self.probe(['811', '1min 30s', 'mixed', 'deactivating',
                            'failed', 'timeout', '0', '2', '9'], [0, 0, 0, 11, 12, 91])
        scope['decky_stop_snapshot'].side_effect = PermissionError('private fixture unavailable')
        report = {}
        with self.assertRaises(AssertionError):
            scope['stop_decky_service']('frame-control-decky.service', report)
        state = report['ownedDeckyStop']
        self.assertEqual(state['result'], 'timeout')
        self.assertEqual(state['beforeStopDiagnostics']['error'],
                         'PermissionError: private fixture unavailable')
        self.assertEqual(state['slowStopDiagnostics'][0]['error'],
                         'PermissionError: private fixture unavailable')


class SlowStopSnapshot(unittest.TestCase):
    def snapshot(self, group):
        path = Path(__file__).resolve().parent / 'decky-runtime/syncthing_service.py'
        function = next(node for node in ast.parse(path.read_text()).body
                        if isinstance(node, ast.FunctionDef) and node.name == 'decky_stop_snapshot')
        scope = dict(Path=Path, os=os, prop=Mock(return_value=group))
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), scope)
        return scope['decky_stop_snapshot']

    def test_owned_cgroup_only_with_bounded_threads_stacks_and_nonconsuming_log_tail(self):
        unit = 'frame-control-migration-decky-fixture.service'
        group = '/user.slice/' + unit
        with tempfile.TemporaryDirectory(prefix='framey-stop-observation-') as directory:
            root = Path(directory)
            cgroups = root / 'cgroup'
            cg = cgroups / group.lstrip('/')
            cg.mkdir(parents=True)
            (cg / 'cgroup.procs').write_text('811\n812\n813\n')
            proc = root / 'proc'
            own, foreign = proc / '811', proc / '812'
            own.mkdir(parents=True)
            foreign.mkdir()
            (own / 'cgroup').write_text('0::' + group + '\n')
            (foreign / 'cgroup').write_text('0::/foreign\n')
            # A foreign process has no inspectable files. A mistaken attempt
            # would yield FileNotFoundError rather than the membership refusal.
            fields = ['S', '100'] + ['0'] * 20
            fields[11], fields[12], fields[19] = '25', '8', '4242'
            (own / 'stat').write_text('811 (fixture (worker)) ' + ' '.join(fields))
            for tid in range(811, 821):
                task = own / 'task' / str(tid)
                task.mkdir(parents=True)
                (task / 'wchan').write_text('poll_schedule_timeout')
                (task / 'stack').write_text('kernel-frame\n' * 1000)
            # Unavailable kernel stacks are evidence limits, not a reason to
            # change ptrace/security settings or abandon the other observations.
            (own / 'task/811/stack').unlink()
            with (root / 'migration-decky.log').open('w+b') as log:
                log.write(b'x' * 20000 + b'last loader phase\n')
                log.flush()
                log.seek(17)
                result = self.snapshot(group)(unit, [log], proc=proc, cgroups=cgroups)
                self.assertEqual(log.tell(), 17)
            first, second, third = result['processes']
            self.assertEqual((first['startTicks'], first['userTicks'], first['systemTicks']), (4242, 25, 8))
            self.assertEqual(len(first['threads']), 8)
            self.assertTrue(first['threadsTruncated'])
            self.assertEqual(first['threads'][0]['stackError'], 'FileNotFoundError')
            self.assertEqual(len(first['threads'][1]['stack']), 4096)
            self.assertEqual(second, {'pid': 812, 'error': 'Process left the owned cgroup; not inspected'})
            self.assertEqual(third, {'pid': 813, 'error': 'FileNotFoundError'})
            self.assertEqual(len(result['logs'][0]['tail'].encode()), 8192)
            self.assertTrue(result['logs'][0]['tail'].endswith('last loader phase\n'))

    def test_refuses_other_units_and_cgroup_traversal_before_proc_reads(self):
        for unit, group in [('foreign.service', '/foreign.service'),
                            ('frame-control-decky.service', '/wrong.service'),
                            ('frame-control-decky.service', '/../../frame-control-decky.service')]:
            with self.subTest(unit=unit, group=group), self.assertRaises(ValueError):
                self.snapshot(group)(unit, [], proc=Path('/unused'), cgroups=Path('/unused'))

    def test_caps_process_count_and_reports_truncation(self):
        unit = 'frame-control-decky.service'
        group = '/' + unit
        with tempfile.TemporaryDirectory(prefix='framey-stop-cap-') as directory:
            root = Path(directory)
            cg = root / unit
            cg.mkdir()
            (cg / 'cgroup.procs').write_text('\n'.join(str(pid) for pid in range(100, 150)))
            result = self.snapshot(group)(unit, [], proc=root / 'absent', cgroups=root)
            self.assertEqual(len(result['processes']), 32)
            self.assertTrue(result['processesTruncated'])
