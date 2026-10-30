"""Instance cleanup tolerates registry lag, but never ignores a live entry."""
import ast
import json
from pathlib import Path
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


class OwnedDeckyStop(unittest.TestCase):
    def probe(self, properties, ticks):
        path = Path(__file__).resolve().parent/'decky-runtime/syncthing_service.py'
        module = ast.parse(path.read_text())
        functions = [node for node in module.body if isinstance(node, ast.FunctionDef)
                     and node.name in ('wait', 'stop_decky_service')]
        scope = dict(json=json, prop=Mock(side_effect=properties), ctl=Mock(), print=Mock(),
                     Path=Mock(return_value=SimpleNamespace(exists=lambda: False)),
                     time=SimpleNamespace(monotonic=Mock(side_effect=ticks), sleep=Mock()),
                     WebSocketException=type('WebSocketException', (Exception,), {}))
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), scope)
        return scope

    def test_manager_completion_after_command_budget_still_requires_clean_result(self):
        scope = self.probe(['811', '1min 30s', 'deactivating', 'inactive', 'success', '0'],
                           [0, 0, 0, 40, 41])
        report = {}
        scope['stop_decky_service']('frame-control-decky.service', report)
        scope['ctl'].assert_called_once_with('stop', '--no-block', 'frame-control-decky.service')
        scope['Path'].assert_called_once_with('/proc/811')
        self.assertEqual(report['ownedDeckyStop']['result'], 'success')
        self.assertEqual(report['ownedDeckyStop']['elapsedSeconds'], 41)

    def test_systemd_forced_timeout_is_not_successful_cleanup(self):
        scope = self.probe(['811', '1min 30s', 'failed', 'timeout', '0'], [0, 0, 0, 91])
        report = {}
        with self.assertRaises(AssertionError):
            scope['stop_decky_service']('frame-control-decky.service', report)
        self.assertEqual(report['ownedDeckyStop']['result'], 'timeout')
        self.assertEqual(report['ownedDeckyStop']['elapsedSeconds'], 91)
        scope['print'].assert_called_once()

    def test_persistent_stop_job_fails_and_retains_last_state(self):
        scope = self.probe(['811', '1min 30s', 'deactivating'], [0, 0, 0, 101, 102])
        report = {}
        with self.assertRaisesRegex(RuntimeError, 'owned Decky service stop'):
            scope['stop_decky_service']('frame-control-decky.service', report)
        self.assertEqual(report['ownedDeckyStop']['activeState'], 'deactivating')
        self.assertNotIn('result', report['ownedDeckyStop'])
        scope['print'].assert_called_once()
