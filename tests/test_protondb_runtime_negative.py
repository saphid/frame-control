"""An expected native failure must retain forced-stop and cleanup evidence."""
import ast
import copy
from pathlib import Path
import unittest


class ProtonDBNegativeStop(unittest.TestCase):
    def verify(self, observation):
        path = Path(__file__).parent / 'decky-runtime/protondb_private.py'
        function = next(node for node in ast.parse(path.read_text()).body
                        if isinstance(node, ast.FunctionDef) and node.name == 'verify_regression_stop')
        scope = {}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), scope)
        scope['verify_regression_stop'](observation)

    def observation(self):
        return dict(cleanShutdownVerified=False, forcedPluginKills=1, loaderReturncode=0,
                    exactDescendantsRemaining={}, errors=[], adoptedChildExits=[{'returncode': 0}],
                    console='original-source forced stop; no unload completion')

    def test_one_or_duplicate_warnings_preserve_the_original_failed_shutdown(self):
        for count in (1, 2):
            with self.subTest(count=count):
                observation = self.observation()
                observation['forcedPluginKills'] = count
                before = copy.deepcopy(observation)
                self.verify(observation)
                self.assertEqual(observation, before, 'raw count must remain intact')
                self.assertFalse(observation['cleanShutdownVerified'])

    def test_missing_regression_or_incomplete_cleanup_cannot_pass(self):
        changes = [dict(forcedPluginKills=0), dict(cleanShutdownVerified=True),
                   dict(loaderReturncode=1), dict(exactDescendantsRemaining={42: {'state': 'S'}}),
                   dict(errors=['Bad file descriptor']), dict(adoptedChildExits=[{'returncode': 1}]),
                   dict(console='Unloaded ProtonDB Badges (v1.3.4)')]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(AssertionError):
                self.verify(dict(self.observation(), **change))
