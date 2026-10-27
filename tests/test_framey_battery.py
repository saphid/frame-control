"""Frame battery names are not the BAT/battery names psutil searches."""
import sandbox  # noqa: F401
import sys
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'ui'))
import framey_battery


class FrameBattery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.battery = self.root/'max1720x_bat_7-36'
        self.battery.mkdir()
        self.psutil = SimpleNamespace(sensors_battery=lambda: None,
                                      POWER_TIME_UNLIMITED=-2, POWER_TIME_UNKNOWN=-1)
        self.patch = patch.dict(sys.modules, {'psutil': self.psutil})
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def files(self, **values):
        for name, value in values.items():
            (self.battery/name).write_text(str(value))

    def test_frame_name_uses_type_capacity_and_status_without_writes(self):
        self.files(type='Battery', capacity=99, status='Full')
        result = framey_battery.sensors_battery(self.root)
        self.assertEqual((result.percent, result.power_plugged, result.secsleft), (99, True, -2))
        self.assertEqual((self.battery/'capacity').read_text(), '99')

    def test_time_to_empty_is_seconds_and_missing_time_stays_unknown(self):
        self.files(type='Battery', capacity=42, status='Discharging', time_to_empty_now=1234)
        self.assertEqual(framey_battery.sensors_battery(self.root).secsleft, 1234)
        (self.battery/'time_to_empty_now').unlink()
        self.assertEqual(framey_battery.sensors_battery(self.root).secsleft, -1)

    def test_unknown_charge_state_is_not_claimed_as_plugged(self):
        self.files(type='Battery', capacity=42, status='Unknown')
        result = framey_battery.sensors_battery(self.root)
        self.assertIsNone(result.power_plugged)
        self.assertEqual(result.secsleft, -1)

    def test_native_psutil_result_is_preserved_and_invalid_supplies_are_ignored(self):
        native = object()
        self.psutil.sensors_battery = lambda: native
        self.assertIs(framey_battery.sensors_battery(self.root), native)
        self.psutil.sensors_battery = lambda: None
        for values in [dict(type='USB', capacity=99, status='Charging'),
                       dict(type='Battery', capacity=101, status='Full'),
                       dict(type='Battery', capacity=50, status='Full', present=0)]:
            self.files(**values)
            self.assertIsNone(framey_battery.sensors_battery(self.root))
        self.assertIsNone(framey_battery.sensors_battery(self.root/'missing'))
