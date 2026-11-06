"""The real-device check must abort before touching a standby or busy Frame."""
import sandbox  # noqa: F401
import contextlib
import importlib.util
import io
import json
import secrets
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch


MODULE = Path(__file__).resolve().parents[1]/'scripts/framey-worn-check.py'
spec = importlib.util.spec_from_file_location('framey_worn_check', MODULE)
worn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worn)


class WornGate(unittest.TestCase):
    def complete_check(self, *, nonce=None, after=None, cleanup_error=None, screenshot_paths=None):
        token = secrets.token_hex(12)
        state = {'battery':[{'percent':99}], 'activity':1, 'proximity':[200.0],
                 'panelService':True, 'plugins':[{'id':14,'name':'Sample'}], 'panel':'registered'}
        interaction = {'nonce':nonce or 'framey-' + token,'started':100.0,
                       'panel':{'at':101.0,'pluginId':14},'input':{'at':102.0}}
        def remote(command, stdin=None, **kwargs):
            if cleanup_error == 'challenge' and 'p.unlink()' in command:
                raise RuntimeError('challenge cleanup failed')
            if cleanup_error == 'lock' and command.startswith('test '):
                raise RuntimeError('lock cleanup failed')
            if stdin == worn.OVERLAY_PROBE:
                return json.dumps({'visible':True})
            if stdin is not None:
                return json.dumps({'path':'/tmp/framey-worn-test-shot.png'})
            return ''
        def run(argv, **kwargs):
            if argv[0] == 'convert':
                if screenshot_paths is not None:
                    screenshot_paths.append(Path(argv[1]))
                self.assertEqual(Path(argv[1]).read_bytes(), b'private synthetic screenshot')
                return SimpleNamespace(returncode=0,stdout=' '.join(f'#{n:06x}' for n in range(10)))
            kwargs['stdout'].write(b'private synthetic screenshot')
            return SimpleNamespace(returncode=0)
        with patch.object(worn.secrets,'token_hex',return_value=token), \
             patch.object(worn,'probe',side_effect=[state,state,after or state]), \
             patch.object(worn,'check_file',return_value=interaction), \
             patch.object(worn,'remote',side_effect=remote) as calls, \
             patch.object(worn.subprocess,'run',side_effect=run), \
             patch.object(worn.time,'time',side_effect=[100.0,103.0,103.0]), \
             patch.object(worn.time,'monotonic',side_effect=[0,1,36]), \
             patch.object(worn.time,'sleep'), contextlib.redirect_stdout(io.StringIO()) as out:
            code = worn.main(worn_confirmed=True)
        report = json.loads(out.getvalue()[out.getvalue().index('{'):])
        return code, report, calls

    def test_foreign_challenge_never_counts_as_this_runs_input(self):
        code, report, calls = self.complete_check(nonce='another-run')
        self.assertEqual(code, 1)
        self.assertFalse(report.get('passed', False))
        self.assertFalse(any(c.kwargs.get('stdin') == worn.OVERLAY_PROBE for c in calls.call_args_list),
                         'no overlay or screenshot request after the challenge times out')

    def test_matching_challenge_and_cleanup_pass_machine_checks_only(self):
        code, report, _ = self.complete_check()
        self.assertEqual(code, 0, report)
        self.assertTrue(report['passed'])
        self.assertTrue(report['lockReleased'])
        self.assertFalse(report['wornVisualComfortVerified'])
        self.assertFalse(report['controllerHardwareVerified'])

    def test_screenshot_uses_local_os_temp_directory_and_cleans_only_its_files(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder)/'unrelated.txt'
            marker.write_bytes(b'keep')
            screenshots = []
            with patch.object(tempfile, 'tempdir', folder):
                code, report, _ = self.complete_check(screenshot_paths=screenshots)
            self.assertEqual(code, 0, report)
            self.assertEqual(len(screenshots), 1)
            self.assertEqual(screenshots[0].parent.parent, Path(folder))
            self.assertFalse(screenshots[0].parent.exists(), 'remove the owned private screenshot directory')
            self.assertEqual(marker.read_bytes(), b'keep')

    def test_cleanup_failures_cannot_return_a_passing_result(self):
        for cleanup in ('challenge', 'lock'):
            with self.subTest(cleanup=cleanup):
                code, report, _ = self.complete_check(cleanup_error=cleanup)
                self.assertEqual(code, 1, report)
                self.assertFalse(report['passed'])

    def test_final_sensor_failure_stops_before_overlay_or_screenshot(self):
        state = {'battery':[{'percent':99}], 'activity':1, 'proximity':[200.0],
                 'panelService':True, 'plugins':[{'id':14,'name':'Sample'}], 'panel':'registered'}
        for changed in ({'proximity':[]}, {'battery':[]}, {'battery':[{'percent':19}]}, {'activity':3}):
            with self.subTest(changed=changed):
                code, report, calls = self.complete_check(after={**state, **changed})
                self.assertEqual(code, 1)
                self.assertIn('changed during the check', report['error'])
                self.assertFalse(any(c.kwargs.get('stdin') == worn.OVERLAY_PROBE for c in calls.call_args_list))

    def test_fresh_evidence_rejects_wrong_start_stale_future_or_malformed_events(self):
        good = {'nonce':'own','started':100.0,'panel':{'pluginId':14,'at':101.0},'input':{'at':102.0}}
        self.assertTrue(worn.fresh_interaction(good, 'own', 100.0, {14}, 103.0))
        for changed in ({'started':99.0}, {'panel':{'pluginId':15,'at':101.0}},
                        {'input':{'at':99.0}}, {'input':{'at':104.0}},
                        {'input':{'at':float('nan')}}, {'input':{'at':float('inf')}},
                        {'panel':None}, {'input':{'at':'102'}}):
            with self.subTest(changed=changed):
                self.assertFalse(worn.fresh_interaction({**good,**changed}, 'own', 100.0, {14}, 103.0))

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
        report = json.loads(out.getvalue())
        self.assertIn('trusted pointer events alone do not prove', report['error'])
        self.assertFalse(report['operatorWornConfirmed'])
        self.assertFalse(report['wornVisualComfortVerified'])
        self.assertFalse(report['controllerHardwareVerified'])
        self.assertIn('no wearer confirmation', report['proof'])

    def test_standby_is_read_only_under_owned_lock_and_releases_it(self):
        state = {'battery':[{'percent':99}], 'activity':3, 'proximity':[6.25], 'panelService':True,
                 'plugins':[{'id':14,'name':'ProtonDB Badges'}], 'panel':None}
        code, report, remote, probe = self.run_gate(state)
        self.assertEqual(code, 1)
        self.assertIn('standby', report)
        evidence = json.loads(report)
        self.assertTrue(evidence['operatorWornConfirmed'])
        self.assertFalse(evidence['wornVisualComfortVerified'])
        self.assertFalse(evidence['controllerHardwareVerified'])
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
