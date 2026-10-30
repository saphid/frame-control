"""Retain the native browser fixture's observed overlapping-list regression."""
import ast
from pathlib import Path
import unittest


class TerminalSnapshots(unittest.TestCase):
    @staticmethod
    def shell_pid(listings):
        path = Path(__file__).parent / 'decky-runtime/terminal_http.py'
        tree = ast.parse(path.read_text())
        tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name == 'started_terminal_pid']
        scope = {}
        exec(compile(tree, str(path), 'exec'), scope)
        return scope['started_terminal_pid']([
            {'request': {'method': 'get_terminals'}, 'response': {'result': items}}
            for items in listings])

    def test_original_ci_race_keeps_one_identity_across_not_started_and_started(self):
        identity = '68ab771c-083d-4a62-94b3-e6df672d182b'
        before = {'id': identity, 'is_started': False, 'is_completed': False}
        after = {**before, 'is_started': True, 'pid': 556}
        # The original request-count assertion rejects this actual CI ordering.
        listings = [[before], [after]]
        self.assertEqual(self.shell_pid(listings), 556)
        self.assertEqual(self.shell_pid([[], [after]]), 556)

    def test_extra_terminal_changed_identity_pid_or_missing_live_shell_still_fail(self):
        live = {'id': 'owned', 'is_started': True, 'is_completed': False, 'pid': 556}
        for listings in ([], [[]], [[live, live]], [[live], [{**live, 'id': 'other'}]],
                         [[live], [{**live, 'pid': 557}]], [[{**live, 'pid': None}]],
                         [[{**live, 'is_started': False}]], [[{**live, 'is_completed': True}]]):
            with self.subTest(listings=listings), self.assertRaises(AssertionError):
                self.shell_pid(listings)
