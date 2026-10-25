"""The real-device check must abort before touching a standby or busy Frame."""
import sandbox  # noqa: F401
import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch


MODULE = Path(__file__).resolve().parents[1]/'scripts/framey-worn-check.py'
spec = importlib.util.spec_from_file_location('framey_worn_check', MODULE)
worn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worn)


class WornGate(unittest.TestCase):
    def run_gate(self, state, remote_side_effect=None):
        out = io.StringIO()
        with patch.object(worn, 'probe', return_value=state), \
                patch.object(worn, 'remote', side_effect=remote_side_effect) as remote, \
                contextlib.redirect_stdout(out):
            result = worn.main()
        return result, out.getvalue(), remote

    def test_standby_never_takes_lock(self):
        state = {'battery':[{'percent':99}], 'activity':3, 'panelService':True,
                 'plugins':[{'id':14,'name':'ProtonDB Badges'}], 'panel':None}
        code, report, remote = self.run_gate(state)
        self.assertEqual(code, 1)
        self.assertIn('standby', report)
        remote.assert_not_called()

    def test_low_battery_never_takes_lock(self):
        state = {'battery':[{'percent':19}], 'activity':0, 'panelService':True,
                 'plugins':[{'id':14,'name':'ProtonDB Badges'}], 'panel':None}
        code, report, remote = self.run_gate(state)
        self.assertEqual(code, 1)
        self.assertIn('below 20%', report)
        remote.assert_not_called()

    def test_foreign_lock_is_never_removed(self):
        state = {'battery':[{'percent':99}], 'activity':0, 'panelService':True,
                 'plugins':[{'id':14,'name':'ProtonDB Badges'}], 'panel':None}
        code, report, remote = self.run_gate(state, RuntimeError('File exists'))
        self.assertEqual(code, 1)
        self.assertIn('File exists', report)
        self.assertEqual(remote.call_count, 1)
        self.assertIn('mkdir /tmp/frame-test.lock', remote.call_args.args[0])
