"""The Frame simulator's stand-ins (tests/fakeframe/sim) answer the way the app reads them.

Runs the stand-ins on this computer against a temporary state folder: the ffmpeg
wrapper's input swap on the app's own live view and recording commands, vrcmd's
output through the app's parsers, and the smoke gate's preflight. No Docker; the
simulator itself is covered by running scripts/frame-sim.sh (docs/testing.md).
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import runpy
import shlex
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sandbox  # noqa: F401  (first: keeps tests off real data and services)

if sys.platform == 'win32':
    raise unittest.SkipTest('the stand-ins run in the Linux simulator; they lock files with fcntl')

ROOT = Path(__file__).resolve().parent.parent
SIM = ROOT / 'tests/fakeframe/sim/rootfs'
sys.path.insert(0, str(ROOT / 'ui'))
sys.path.insert(0, str(ROOT / 'tests/fakeframe/rootfs/usr/local/lib/fakeframe'))
sys.path.insert(0, str(SIM / 'usr/local/lib/fakeframe/sim'))
import fakeframe_state  # noqa: E402
import frame_clips  # noqa: E402
import frame_panels  # noqa: E402
import frame_status  # noqa: E402
import scene  # noqa: E402
import server  # noqa: E402
import simstate  # noqa: E402

VRCMD = SIM / 'opt/steamvr/bin/linuxarm64/vrcmd'


def load_wrapper():
    loader = importlib.machinery.SourceFileLoader('sim_ffmpeg', str(SIM / 'usr/local/bin/ffmpeg'))
    spec = importlib.util.spec_from_loader('sim_ffmpeg', loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def ffmpeg_args(command):
    """The arguments of the first ffmpeg in a shell command line, up to its `&`."""
    return shlex.split(command.split('ffmpeg ', 1)[1].split(' & ', 1)[0])


class SimState(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp(prefix='frame-sim-test-')
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        patches = [mock.patch.object(simstate, 'DIR', tmp),
                   mock.patch.object(simstate, 'STATE', tmp + '/state.json'),
                   mock.patch.object(simstate, 'LOCK', tmp + '/state.lock'),
                   mock.patch.object(simstate, 'SCREEN_TEXT', tmp + '/screen.txt'),
                   mock.patch.object(fakeframe_state, 'DIR', tmp),
                   mock.patch.object(fakeframe_state, 'STATE', tmp + '/fake.json'),
                   mock.patch.object(fakeframe_state, 'LOCK', tmp + '/fake.lock'),
                   mock.patch.object(fakeframe_state, 'CALLS', tmp + '/calls.jsonl')]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def vrcmd(self, *args):
        out = io.StringIO()
        with mock.patch.object(sys, 'argv', [str(VRCMD), *args]), contextlib.redirect_stdout(out):
            try:
                runpy.run_path(str(VRCMD), run_name='__main__')
            except SystemExit as e:
                if e.code not in (None, 0):
                    raise AssertionError(f'vrcmd {args}: {e.code}')
        return out.getvalue()


class FfmpegWrapper(SimState):
    def setUp(self):
        super().setUp()
        self.wrapper = load_wrapper()

    def test_live_view_reads_the_scene_instead_of_the_v4l2_device(self):
        args = ffmpeg_args(server.stream_command('h=720&fps=30'))
        out, swapped = self.wrapper.rewrite(args)
        self.assertEqual([s['kind'] for s in swapped], ['v4l2'])
        self.assertEqual(swapped[0]['source'], server.STREAM_DEVICE)
        self.assertNotIn('v4l2', out)
        self.assertNotIn(server.STREAM_DEVICE, out)
        i = out.index('lavfi')
        self.assertEqual(out[i - 2:i + 3], ['-re', '-f', 'lavfi', '-i', scene.graph(30)])
        # Everything after the input (scaling, x264, output to stdout) is the app's own.
        self.assertEqual(out[out.index('-vf'):], args[args.index('-vf'):])

    def test_recording_swaps_video_and_sound_and_keeps_their_clock_options(self):
        args = ffmpeg_args(frame_clips.record_command('rec-20261030-075857', True))
        out, swapped = self.wrapper.rewrite(args)
        self.assertEqual([s['kind'] for s in swapped], ['v4l2', 'pulse'])
        self.assertEqual(out.count('-use_wallclock_as_timestamps'), 2)
        self.assertEqual(out.count('lavfi'), 2)
        self.assertIn(self.wrapper.TONE, out)
        self.assertNotIn('pulse', out)

    def test_panel_window_capture_reads_the_scene_at_its_frame_rate(self):
        args = ffmpeg_args(server.stream_command('src=panel&window=10485777&display=:1&h=720&fps=60'))
        out, swapped = self.wrapper.rewrite(args)
        self.assertEqual(swapped[0]['kind'], 'x11grab')
        self.assertIn(scene.graph(60), out)
        self.assertNotIn('-window_id', out)

    def test_other_ffmpeg_uses_pass_through(self):
        args = ['-hide_banner', '-i', 'rec.mkv', '-map', '0', '-c', 'copy', 'rec.mp4']
        self.assertEqual(self.wrapper.rewrite(args), (args, []))

    def test_live_view_fails_like_a_missing_device_when_steamvr_is_off(self):
        with simstate.update() as s:
            s['vr'] = False
        with self.assertRaises(SystemExit) as e:
            self.wrapper.rewrite(ffmpeg_args(server.stream_command('h=720&fps=30')))
        self.assertIn('No such device', str(e.exception.code))


class Vrcmd(SimState):
    def test_stats_give_the_activity_level_the_app_and_smoke_preflight_read(self):
        for worn, level in ((False, 3), (True, 1)):
            with self.subTest(worn=worn):
                with simstate.update() as s:
                    s['worn'] = worn
                with mock.patch.object(frame_status, 'run', lambda *a: self.vrcmd('--stats')):
                    self.assertEqual(frame_status.activity_level(), level)

    def test_overlays_parse_and_showdashboard_switches_the_visible_panel(self):
        panels = frame_panels.parse_overlays(self.vrcmd('--overlays'))
        self.assertEqual([(p['key'], p['visible']) for p in panels],
                         [('valve.steam.bigpicture', True), ('valve.steam.desktop', False)])
        self.vrcmd('--showdashboard', 'valve.steam.desktop')
        panels = frame_panels.parse_overlays(self.vrcmd('--overlays'))
        self.assertEqual([p['key'] for p in panels if p['visible']], ['valve.steam.desktop'])

    def test_vr_off_fails_every_command(self):
        with simstate.update() as s:
            s['vr'] = False
        with self.assertRaises(AssertionError):
            self.vrcmd('--stats')


class ScreenText(SimState):
    def test_names_the_running_title_and_keeps_percent_signs(self):
        with fakeframe_state.update() as s:
            s['launches'].append({'appid': 620980, 'started': True, 'exit': None})
        scene.text()
        text = Path(simstate.SCREEN_TEXT).read_text()
        self.assertIn('Playing: Beat Saber', text)
        self.assertIn('Battery 76% Charging', text)
        # drawtext would read "%" as an expansion; the graph turns that off.
        self.assertIn('expansion=none', scene.graph(30))
        self.assertIn('reload=1', scene.graph(30))


class SmokeGate(unittest.TestCase):
    def test_the_smoke_test_marks_runs_on_a_fake_frame(self):
        smoke = (ROOT / 'tests/smoke/frame_smoke.py').read_text()
        mark = 'FAKEFRAME_MARK = '
        path = smoke.split(mark, 1)[1].split()[0].strip("'")
        self.assertTrue((ROOT / 'tests/fakeframe/rootfs' / path.lstrip('/')).is_file(),
                        'the file frame_smoke.py looks for must exist on every fake Frame')
        self.assertIn("'simulated': simulated", smoke)


if __name__ == '__main__':
    unittest.main()
