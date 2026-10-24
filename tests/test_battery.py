"""Read-only sysfs battery parsing; fixture values, no real headset access."""
import sandbox  # noqa: F401
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ui'))
import frame_status as status


class Battery(unittest.TestCase):
    def probe(self, fields):
        # Real files exercise missing files, whitespace and integer conversion.
        with tempfile.TemporaryDirectory() as tmp:
            node = Path(tmp) / 'max1720x_bat_7-36'
            node.mkdir()
            for name, value in dict(type='Battery', **fields).items():
                (node / name).write_text(str(value) + '\n')
            with mock.patch.object(status.glob, 'glob', return_value=[str(node)]):
                result = status.battery()
            if result:
                result.pop('source')
            return result

    def test_frame_units_and_optional_health(self):
        b = self.probe(dict(capacity=73, status='Charging', voltage_now=3800000,
                            current_now=1000000, temp=325, health='Good',
                            charge_full=4600000, charge_full_design=5000000,
                            cycle_count=42, time_to_full_now=3600))
        self.assertEqual(b, dict(percent=73, status='Charging', watts=3.8,
                                tempC=32.5, health='Good', timeToFull=3600,
                                timeToEmpty=None, cycleCount=42, fullMah=4600,
                                designMah=5000, capacityHealthPercent=92))

    def test_zero_negative_current_and_temperature(self):
        b = self.probe(dict(capacity=0, cycle_count=0, temp=-50,
                            voltage_now=3800000, current_now=-1000000))
        self.assertEqual((b['percent'], b['cycleCount'], b['tempC'], b['watts']),
                         (0, 0, -5, -3.8))

    def test_missing_optional_sensors_stay_null(self):
        b = self.probe(dict(capacity=50, status='Discharging'))
        self.assertEqual(b['percent'], 50)
        self.assertTrue(all(value is None for key, value in b.items()
                            if key not in ('percent', 'status')))

    def test_invalid_values_do_not_break_other_readings(self):
        for invalid in ('abc', '', '-1', '101', '12.5'):
            b = self.probe(dict(capacity=invalid, status='Charging', temp='bad',
                                charge_full=4500000, charge_full_design=0,
                                time_to_full_now=-1, time_to_empty_now=4294967295,
                                cycle_count=-1, voltage_now='bad', current_now=100))
            self.assertIsNone(b['percent'])
            for key in ('watts', 'tempC', 'capacityHealthPercent', 'timeToFull', 'timeToEmpty', 'cycleCount'):
                self.assertIsNone(b[key], key)
            self.assertEqual(b['status'], 'Charging')

    def test_no_battery_and_unreadable_type(self):
        with mock.patch.object(status.glob, 'glob', return_value=[]):
            self.assertIsNone(status.battery())
        with mock.patch.object(status.glob, 'glob', return_value=['/missing']), \
                mock.patch('builtins.open', side_effect=PermissionError):
            self.assertIsNone(status.battery())

    def test_prefers_frame_and_excludes_peripheral_or_absent_batteries(self):
        paths = ['/sys/class/power_supply/aaa', '/sys/class/power_supply/max1720x_bat_7-36']
        def read(path):
            return {'type': 'Battery', 'capacity': '80'}.get(path.rsplit('/', 1)[-1])
        with mock.patch.object(status.glob, 'glob', return_value=paths), \
                mock.patch.object(status, 'read', side_effect=read):
            self.assertEqual(status.battery()['source'], paths[1])
        self.assertIsNone(self.probe(dict(scope='Device', capacity=99)))
        self.assertIsNone(self.probe(dict(present=0, capacity=99)))

    def test_permission_failure_affects_only_one_sensor(self):
        actual_open = open
        def guarded(path, *args, **kwargs):
            if str(path).endswith('/temp'):
                raise PermissionError('unreadable')
            return actual_open(path, *args, **kwargs)
        with mock.patch('builtins.open', side_effect=guarded):
            b = self.probe(dict(capacity=45, temp=300))
        self.assertEqual(b['percent'], 45)
        self.assertIsNone(b['tempC'])
