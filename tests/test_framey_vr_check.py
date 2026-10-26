"""Safety gates for unattended device work; no headset or OpenVR loaded."""
import importlib.util
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1]/'scripts/framey-vr-check.py'
spec = importlib.util.spec_from_file_location('framey_vr_check', PATH)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


class Safety(unittest.TestCase):
    def test_foreign_lock_prevents_sensor_reads_and_cleanup(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(check, 'Remote') as factory:
            remote = factory.return_value
            remote.side_effect = RuntimeError('File exists')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(check.main(['--exercise','--output',folder]), 1)
            remote.python.assert_not_called()
            self.assertEqual(remote.call_count, 1)
            self.assertIn('mkdir /tmp/frame-test.lock', remote.call_args.args[0])
            self.assertFalse(json.loads((Path(folder)/'result.json').read_text())['passed'])

    def test_low_battery_never_wakes_or_installs_and_releases_lock(self):
        state = {'battery':[19], 'pause':'power.pauseCompositorOnStandby=true',
                 'timeout':'power.turnOffScreensTimeout=17.000000','dashboardVisible':False}
        with tempfile.TemporaryDirectory() as folder, patch.object(check, 'Remote') as factory, \
                patch.object(check.frame_decky, 'change') as install:
            remote = factory.return_value
            remote.python.return_value = state
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(check.main(['--exercise','--output',folder]), 1)
            install.assert_not_called()
            self.assertEqual(remote.call_count, 2)
            self.assertIn('rmdir /tmp/frame-test.lock', remote.call_args.args[0])
            self.assertFalse(any('--handlewakeup' in c.args[0] for c in remote.call_args_list))

    def test_power_restore_after_partial_setter_failure(self):
        state = {'battery':[99], 'pause':'power.pauseCompositorOnStandby=true',
                 'timeout':'power.turnOffScreensTimeout=17.000000','dashboardVisible':False,
                 'stats':[{'activity_level':3}], 'proximity':[6.25]}
        with tempfile.TemporaryDirectory() as folder, patch.object(check, 'Remote') as factory:
            remote = factory.return_value
            remote.python.return_value = state
            def run(cmd, **_):
                if '--set-settings-float power.turnOffScreensTimeout 120' in cmd:
                    raise RuntimeError('setter failed')
                return ''
            remote.side_effect = run
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(check.main(['--wake','--output',folder]), 1)
            commands = [c.args[0] for c in remote.call_args_list]
            self.assertTrue(any('--set-settings-bool power.pauseCompositorOnStandby 1' in c for c in commands))
            self.assertTrue(any('--set-settings-float power.turnOffScreensTimeout 17.000000' in c for c in commands))
            self.assertIn('rmdir /tmp/frame-test.lock', commands[-1])

    def test_awake_or_unknown_activity_refuses_wake_and_install(self):
        for stats in ([{'activity_level':1}], [{'activity_level':2}], [], None):
            state = {'battery':[99], 'pause':'power.pauseCompositorOnStandby=true',
                     'timeout':'power.turnOffScreensTimeout=17.000000',
                     'dashboardVisible':False, 'stats':stats, 'proximity':[0.0]}
            for mode in ('--wake', '--exercise'):
                with self.subTest(stats=stats, mode=mode), \
                     tempfile.TemporaryDirectory() as folder, \
                     patch.object(check, 'Remote') as factory, \
                     patch.object(check.frame_decky, 'change') as install:
                    remote = factory.return_value
                    remote.python.return_value = state
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(check.main([mode,'--output',folder]), 1)
                    install.assert_not_called()
                    commands = [c.args[0] for c in remote.call_args_list]
                    self.assertEqual(len(commands), 2)
                    self.assertIn('mkdir /tmp/frame-test.lock', commands[0])
                    self.assertIn('rmdir /tmp/frame-test.lock', commands[-1])
                    report = json.loads((Path(folder)/'result.json').read_text())
                    self.assertIn('active session untouched', report['error'])

    def test_exact_linux_event_abi_and_debug_profile(self):
        import ctypes
        overlay_spec = importlib.util.spec_from_file_location('framey_openvr', PATH.with_name('framey_openvr.py'))
        overlay = importlib.util.module_from_spec(overlay_spec); overlay_spec.loader.exec_module(overlay)
        self.assertEqual(ctypes.sizeof(overlay.Event), 60)
        self.assertEqual(overlay.Event.data.offset, 12)
        original = check.frame_headset.bundle()
        patched = check.debug_bundle(original, '/tmp/owned-profile')
        import tarfile
        with tarfile.open(fileobj=io.BytesIO(patched),mode='r:gz') as archive:
            source=archive.extractfile('ui/frame_headset_runtime.py').read().decode()
        self.assertIn("'--remote-debugging-port=0'", source)
        self.assertIn("'/tmp/owned-profile'", source)
        self.assertNotIn("str(BASE / 'profile')", source)
