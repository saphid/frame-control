"""The real-device check must abort before touching a standby or busy Frame."""
import sandbox  # noqa: F401
import contextlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


MODULE = Path(__file__).resolve().parents[1]/'scripts/framey-worn-check.py'
spec = importlib.util.spec_from_file_location('framey_worn_check', MODULE)
worn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worn)


class WornGate(unittest.TestCase):
    def run_gate(self, state, remote_side_effect=None):
        out = io.StringIO()
        with patch.object(worn, 'probe', return_value=state) as probe, \
                patch.object(worn, 'remote', side_effect=remote_side_effect) as remote, \
                contextlib.redirect_stdout(out):
            result = worn.main(worn_confirmed=True)
        return result, out.getvalue(), remote, probe

    def test_no_wearer_confirmation_means_no_sensor_or_input_claim(self):
        with patch.object(worn,'remote') as remote, contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(worn.main(),1)
        remote.assert_not_called()
        self.assertIn('trusted pointer events alone do not prove',out.getvalue())

    def test_standby_is_read_only_under_owned_lock_and_releases_it(self):
        state = {'battery':[{'percent':99}], 'activity':3, 'proximity':[6.25], 'panelService':True,
                 'plugins':[{'id':14,'name':'ProtonDB Badges'}], 'panel':None}
        code, report, remote, probe = self.run_gate(state)
        self.assertEqual(code, 1)
        self.assertIn('standby', report)
        probe.assert_called_once()
        self.assertEqual(remote.call_count, 2)
        self.assertIn('mkdir /tmp/frame-test.lock', remote.call_args_list[0].args[0])
        self.assertIn('rmdir /tmp/frame-test.lock', remote.call_args_list[1].args[0])

    def test_low_battery_releases_owned_lock(self):
        state = {'battery':[{'percent':19}], 'activity':0, 'proximity':[6.25], 'panelService':True,
                 'plugins':[{'id':14,'name':'ProtonDB Badges'}], 'panel':None}
        code, report, remote, probe = self.run_gate(state)
        self.assertEqual(code, 1)
        self.assertIn('below 20%', report)
        probe.assert_called_once()
        self.assertEqual(remote.call_count, 2)

    def test_foreign_lock_prevents_all_sensor_reads_and_is_never_removed(self):
        state = {'battery':[{'percent':99}], 'activity':0, 'proximity':[6.25], 'panelService':True,
                 'plugins':[{'id':14,'name':'ProtonDB Badges'}], 'panel':None}
        code, report, remote, probe = self.run_gate(state, RuntimeError('File exists'))
        self.assertEqual(code, 1)
        self.assertIn('File exists', report)
        probe.assert_not_called()
        self.assertEqual(remote.call_count, 1)
        self.assertIn('mkdir /tmp/frame-test.lock', remote.call_args.args[0])

    def test_screenshot_palette_counts_distinct_colors(self):
        self.assertEqual(worn.color_count('0 #ff00aa 1 #ff00aa 2 #00ff00'), 2)

    def test_missing_proximity_stops_before_panel_or_input_and_releases_lock(self):
        state = {'battery':[{'percent':99}], 'activity':0, 'proximity':[],
                 'panelService':True, 'plugins':[{'id':14,'name':'ProtonDB Badges'}], 'panel':None}
        code, report, remote, probe = self.run_gate(state)
        self.assertEqual(code, 1)
        self.assertIn('Proximity reading unavailable', report)
        probe.assert_called_once()
        self.assertEqual(remote.call_count, 2)
        self.assertIn('rmdir /tmp/frame-test.lock', remote.call_args_list[-1].args[0])

    def test_proximity_disappearing_on_second_read_stops_before_input(self):
        first = {'battery':[{'percent':99}], 'activity':0, 'proximity':[200.0],
                 'panelService':True, 'plugins':[{'id':14,'name':'ProtonDB Badges'}], 'panel':None}
        second = {**first, 'proximity':[]}
        out = io.StringIO()
        with patch.object(worn, 'probe', side_effect=[first, second]) as probe, \
                patch.object(worn, 'remote') as remote, contextlib.redirect_stdout(out):
            code = worn.main(worn_confirmed=True)
        self.assertEqual(code, 1)
        self.assertIn('Activity, proximity or battery changed', out.getvalue())
        self.assertEqual(probe.call_count, 2)
        self.assertEqual(remote.call_count, 2)

    def test_probe_reads_activity_from_status_after_metrics(self):
        rows = [{'operation':'performance','frame_presents':12},
                {'operation':'status','activity_level':1}]
        def run(argv, **_):
            if argv[-1] == '--stats':
                return SimpleNamespace(returncode=0, stdout=json.dumps(rows))
            return SimpleNamespace(returncode=1, stdout='')
        for current, expected in (
            (rows, 1),
            ([{'operation':'performance','frame_presents':12}], None),
            (rows + [{'operation':'status','activity_level':3}], None),
        ):
            with self.subTest(rows=current):
                rows = current
                out = io.StringIO()
                with patch('subprocess.run', side_effect=run), contextlib.redirect_stdout(out):
                    exec(worn.PROBE, {})
                result = json.loads(out.getvalue())
                self.assertEqual(result['activity'], expected)
                self.assertIsInstance(result['proximity'], list)

    def test_probe_discards_nonfinite_proximity(self):
        def glob(_path, pattern):
            return [SimpleNamespace(read_text=lambda: 'nan')] if pattern == 'iio:device*/in_proximity_raw' else []
        with patch('pathlib.Path.glob', autospec=True, side_effect=glob), \
                patch('subprocess.run', return_value=SimpleNamespace(returncode=1, stdout='')), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            exec(worn.PROBE, {})
        self.assertEqual(json.loads(out.getvalue())['proximity'], [])
