"""Power sampler fixtures and SSH transport contract; no real device contact."""
import sandbox  # noqa: F401
import contextlib
import csv
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('power_sample', ROOT / 'scripts/frame_power_sample.py')
power = importlib.util.module_from_spec(spec)
spec.loader.exec_module(power)
sys.path.insert(0, str(ROOT / 'ui'))
import frame_status as status


class Sampler(unittest.TestCase):
    def patch(self, obj, name, **kwargs):
        p = mock.patch.object(obj, name, **kwargs)
        result = p.start()
        self.addCleanup(p.stop)
        return result

    def fixture(self, files):
        for path, value in files.items():
            node = self.root / path.lstrip('/')
            node.parent.mkdir(parents=True, exist_ok=True)
            node.write_text(str(value))
        actual_glob = power.glob.glob
        def paths(pattern):
            return [str(p)[len(str(self.root)):] for p in actual_glob(str(self.root) + pattern)]
        actual_read = power.read
        self.patch(power.glob, 'glob', side_effect=paths)
        self.patch(power, 'read', side_effect=lambda p: actual_read(str(self.root) + str(p)))
        self.patch(status, 'read', side_effect=lambda p: actual_read(str(self.root) + str(p)))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        p = mock.patch.object(power, 'LOCK', self.root / 'lock')
        p.start()
        self.addCleanup(p.stop)

    def test_real_file_units_zero_signed_battery_and_named_sensors(self):
        h = '/sys/class/hwmon/hwmon88'
        b = '/sys/class/power_supply/max1720x_bat_7-36'
        self.fixture({h + '/name': 'max34417_9_10', h + '/power1_label': 'vph',
                      h + '/power1_input': '4710000',
                      '/sys/class/hwmon/hwmon3/name': 'slg4ax46073v',
                      '/sys/class/hwmon/hwmon3/fan1_input': '0',
                      '/sys/class/hwmon/hwmon3/pwm1': '41',
                      '/sys/class/thermal/thermal_zone9/type': 'cpu3_top_thermal',
                      '/sys/class/thermal/thermal_zone9/temp': '45321',
                      b + '/type': 'Battery', b + '/capacity': '0', b + '/status': 'Discharging',
                      b + '/voltage_now': '3800000', b + '/current_now': '-1000000',
                      '/proc/stat': 'cpu  10 0 0 90 0 0 0 0'})
        sample, ticks = power.snapshot(status, (80, 80))
        r = sample['readings']
        self.assertEqual(r['rail.max34417_9_10.vph.power1']['value'], 4.71)
        self.assertEqual(r['battery.percent']['value'], 0)
        self.assertEqual(r['battery.watts']['value'], -3.8)
        self.assertEqual(r['battery.status']['value'], 'Discharging')
        self.assertEqual(r['fan.slg4ax46073v.fan1_input']['value'], 0)
        self.assertEqual(r['fan.pwmRaw']['unit'], 'raw')
        self.assertEqual(r['thermal.cpu3_top_thermal.thermal_zone9']['value'], 45.321)
        self.assertEqual(r['cpu.percent']['value'], 50)
        self.assertEqual(ticks, (100, 90))
        self.assertEqual(sample['unavailableGroups'], ['board', 'charger', 'proximity'])

    def test_missing_and_invalid_values_remain_unavailable(self):
        self.fixture({'/sys/class/thermal/thermal_zone0/temp': '999999999',
                      '/sys/class/hwmon/hwmon2/name': 'fan',
                      '/sys/class/hwmon/hwmon2/fan1_input': '-1'})
        sample, ticks = power.snapshot(status, None)
        self.assertIsNone(ticks)
        self.assertTrue(all(r['value'] is None for r in sample['readings'].values()))
        self.assertEqual(len(sample['unavailableGroups']), 6)
        self.assertIn('two valid CPU', sample['readings']['cpu.percent']['state'])

    def test_permission_error_is_unavailable(self):
        with mock.patch.object(Path, 'read_text', side_effect=PermissionError):
            self.assertIsNone(power.number('/unreadable'))
        for value in ('NaN', 'Infinity', '1.5', '', '9' * 5000):
            with mock.patch.object(power, 'read', return_value=value):
                self.assertIsNone(power.number('/invalid'))

    def test_iio_units_and_permission_denied_proximity(self):
        node = '/sys/bus/iio/devices/iio:device8'
        self.fixture({node + '/name': 'vcnl4000',
                      node + '/in_temp_pcba_at_wifi_input': '37500',
                      node + '/in_current_pm8550b_iin_fb_input': '241671',
                      '/etc/os-release': 'BUILD_ID=20261015.6141207\n'})
        # exists() is used only for optional known charger channels and lock.
        exists = Path.exists
        with mock.patch.object(Path, 'exists', lambda p: exists(p) if p == power.LOCK
                               else exists(self.root / str(p).lstrip('/'))):
            sample, _ = power.snapshot(status, None)
        self.assertEqual(sample['osBuild'], '20261015.6141207')
        self.assertEqual(sample['readings']['board.iio:device8.in_temp_pcba_at_wifi_input']['value'], 37.5)
        self.assertEqual(sample['readings']['charger.iio:device8.iin']['value'], 0.241671)
        self.assertIsNone(sample['readings']['proximity.raw']['value'])
        self.assertIn('proximity', sample['unavailableGroups'])

    def test_unknown_charging_state_is_not_claimed(self):
        self.fixture({})
        with mock.patch.object(status, 'battery', return_value={'status': 'Unknown', 'percent': 50}):
            r = power.snapshot(status, None)[0]['readings']
        self.assertIsNone(r['battery.status']['value'])
        self.assertEqual(r['battery.percent']['value'], 50)

    def test_smoke_lock_prevents_any_sensor_reads(self):
        power.LOCK.mkdir()
        with mock.patch.object(status, 'cpu_ticks') as ticks:
            with self.assertRaisesRegex(RuntimeError, 'Smoke session'):
                power.snapshot(status, None)
        ticks.assert_not_called()

    def test_smoke_lock_appearing_between_samples_stops_and_preserves_partial_report(self):
        self.fixture({'/proc/stat': 'cpu  10 0 0 90 0 0 0 0'})
        with mock.patch.object(power.time, 'sleep', side_effect=lambda _: power.LOCK.mkdir()):
            report = power.collect(status, 3, 1)
        self.assertEqual(len(report['samples']), 1)
        self.assertIn('Smoke session', report['stopped'])
        self.assertEqual(report['requestedSamples'], 3)

    def test_summaries_ignore_missing_values_and_keep_state_changes(self):
        def row(value, unit='W'):
            return {'value': value, 'unit': unit, 'source': '/sensor', 'state': 'available'}
        samples = [{'readings': {'rail': row(0), 'state': row('Charging', 'state')}},
                   {'readings': {'rail': row(None), 'state': row('Full', 'state')}},
                   {'readings': {'rail': row(6)}}]
        summary = power.summarize(samples)
        self.assertEqual(summary['rail'], dict(unit='W', sources=['/sensor'], available=2,
                                              unavailable=1, min=0, max=6, mean=3, first=0, last=6))
        self.assertEqual(summary['state']['states'], ['Charging', 'Full'])
        self.assertEqual(summary['state']['unavailable'], 1)

    def test_csv_quoting_and_unavailable_groups(self):
        report = {'samples': [{'time': 1, 'elapsedSeconds': 0,
                              'readings': {'fan,test': {'value': -3.8, 'unit': 'W',
                                                       'source': '=formula', 'state': 'available'}},
                              'unavailableGroups': ['thermal']}]}
        rows = list(csv.reader(io.StringIO(power.csv_samples(report))))
        self.assertEqual(rows[1][2:6], ['fan,test', '-3.8', 'W', "'=formula"])
        self.assertEqual(rows[2][-1], power.UNAVAILABLE)

    def test_bounded_arguments_rejected_before_ssh(self):
        for args in (['--count', '0'], ['--count', '721'], ['--interval', 'nan'],
                     ['--interval', 'inf'], ['--interval', '0.5'], ['--interval', '61']):
            with mock.patch.object(power.subprocess, 'run') as run, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    power.main(args)
            run.assert_not_called()

    def test_local_lock_prevents_ssh(self):
        power.LOCK.mkdir()
        with mock.patch.object(power.subprocess, 'run') as run, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(power.main([]), 75)
        run.assert_not_called()

    def test_ssh_payload_runs_as_module_and_outputs_report(self):
        report = dict(samples=[], summary={}, stopped=None)
        def ssh(command, **kwargs):
            self.assertIn('BatchMode=yes', command)
            self.assertIn('StrictHostKeyChecking=yes', command)
            self.assertIn('frame', command)
            self.assertEqual(command[-4:], ['--count', '2', '--interval', '1.0'])
            # Execute the exact transmitted source, with main suppressed. Its
            # frame_status module must be importable without running status().
            namespace = {'__name__': 'payload_test'}
            with mock.patch.dict(sys.modules):
                exec(compile(kwargs['input'], '<ssh-stdin>', 'exec'), namespace)
                remote = sys.modules['frame_status']
                self.assertTrue(callable(remote.battery))
                with mock.patch.object(remote, 'status', side_effect=AssertionError('full status forbidden')), \
                     mock.patch.object(remote, 'battery', return_value=None), \
                     mock.patch.object(remote, 'cpu_ticks', return_value=(100, 90)), \
                     mock.patch.object(namespace['glob'], 'glob', return_value=[]), \
                     mock.patch.object(namespace['Path'], 'exists', return_value=False):
                    report.update(namespace['collect'](remote, 1, 1))
            return subprocess.CompletedProcess(command, 0, json.dumps(report), '')
        output = io.StringIO()
        with mock.patch.object(power.subprocess, 'run', side_effect=ssh), contextlib.redirect_stdout(output):
            self.assertEqual(power.main(['--count', '2', '--interval', '1']), 0)
        self.assertEqual(len(json.loads(output.getvalue())['samples']), 1)

    def test_ssh_failures_are_not_measurements(self):
        for result in (subprocess.CompletedProcess([], 255, '', 'offline'),
                       subprocess.CompletedProcess([], 0, 'bad json', '')):
            output = io.StringIO()
            with mock.patch.object(power.subprocess, 'run', return_value=result), \
                 contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                self.assertNotEqual(power.main([]), 0)
            self.assertEqual(output.getvalue(), '')
