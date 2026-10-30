"""Instance cleanup tolerates registry lag, but never ignores a live entry."""
import ast
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
