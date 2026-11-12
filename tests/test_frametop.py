"""Frametop: the Capture view's third desktop (ui/frame_frametop.py, the server routes and events).

Run: python3 -m unittest discover -s tests
"""
import sandbox  # noqa: F401  (first: keeps tests off real data and services)
import base64
import json
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ui"))


class Events(unittest.TestCase):
    """frametop_event: touch_event's gestures with the Frametop screen they are aimed at."""

    @classmethod
    def setUpClass(cls):
        import server
        cls.s = server

    def test_keeps_known_fields(self):
        ev = self.s.frametop_event
        self.assertEqual(ev({"screen": "WL-0", "fx": 0.5, "fy": 0.25}),
                         {"screen": "WL-0", "fx": 0.5, "fy": 0.25})
        self.assertEqual(ev({"screen": "WL-1", "button": "left", "down": False}),
                         {"screen": "WL-1", "button": "left", "down": False})
        self.assertEqual(ev({"screen": "WL-0", "button": "middle"}),
                         {"screen": "WL-0", "button": "middle", "down": True})
        self.assertEqual(ev({"screen": "WL-0", "scroll": [0, 120]}), {"screen": "WL-0", "scroll": [0.0, 120.0]})
        self.assertEqual(ev({"screen": "WL-0", "key": 30}), {"screen": "WL-0", "key": 30, "down": True})
        self.assertEqual(ev({"screen": "WL-0", "text": "hello"}), {"screen": "WL-0", "text": "hello"})
        # Unknown fields are dropped, as touch_event does; a bare screen name is not enough.
        self.assertEqual(ev({"screen": "WL-0", "dx": 3, "other": 1}), {"screen": "WL-0", "dx": 3.0})

    def test_ranges_are_clamped_like_touch(self):
        ev = self.s.frametop_event
        self.assertEqual(ev({"screen": "WL-0", "fx": 2, "fy": -3}),
                         {"screen": "WL-0", "fx": 1.0, "fy": -1.0})
        self.assertEqual(ev({"screen": "WL-0", "dx": 1e9, "dy": -1e9}),
                         {"screen": "WL-0", "dx": self.s.INPUT_MOVE_LIMIT, "dy": -self.s.INPUT_MOVE_LIMIT})
        self.assertEqual(ev({"screen": "WL-0", "scroll": [0, 1e9]}), {"screen": "WL-0", "scroll": [0.0, 5000.0]})

    def test_rejects_bad_events(self):
        bad = [
            None, [], "a", 5, {},
            {"fx": 0.5, "fy": 0.5},                      # a position without its screen
            {"button": "left"},                          # a press without its screen
            {"screen": ""}, {"screen": "WL 0"}, {"screen": "a;rm"}, {"screen": "x" * 40},
            {"screen": "-WL-0"}, {"screen": 7}, {"screen": "WL-0", "fx": "0.5", "fy": 0},
            {"screen": "WL-0", "fx": float("nan"), "fy": 0},
            {"screen": "WL-0", "button": "sideways"},
            {"screen": "WL-0", "key": 0}, {"screen": "WL-0", "key": 999}, {"screen": "WL-0", "key": True},
            {"screen": "WL-0", "scroll": [1]}, {"screen": "WL-0", "scroll": "nope"},
            {"screen": "WL-0", "text": ""}, {"screen": "WL-0", "text": "x" * (self.s.INPUT_TEXT_LIMIT + 1)},
            {"screen": "WL-0"},                          # names a screen, does nothing on it
        ]
        for event in bad:
            with self.assertRaises(self.s.Failure, msg=repr(event)):
                self.s.frametop_event(event)


class FakeAgent:
    """Stands in for _touch / _frametop_input: records batches, returns a chosen state."""

    def __init__(self, state="ready", sent=True):
        self.state, self.sent, self.calls = state, sent, []

    def send(self, events):
        self.calls.append(events)
        return {"state": self.state, "sent": self.sent}


class Routing(unittest.TestCase):
    """remote_touch: screen-bearing events go to the Frametop agent, the rest to the panel agent."""

    @classmethod
    def setUpClass(cls):
        import server
        cls.s = server

    def setUp(self):
        self.panel, self.frametop = FakeAgent(), FakeAgent()
        patch = mock.patch.multiple(self.s, _touch=self.panel, _frametop_input=self.frametop)
        patch.start()
        self.addCleanup(patch.stop)

    def test_a_mixed_batch_reaches_both_agents(self):
        out = self.s.remote_touch({"events": [
            {"dx": 3},
            {"screen": "WL-0", "fx": 0.5, "fy": 0.25},
            {"button": "left", "window": 7, "display": ":1"},
            {"screen": "WL-1", "key": 30},
        ]})
        self.assertEqual(self.frametop.calls, [[{"screen": "WL-0", "fx": 0.5, "fy": 0.25},
                                                {"screen": "WL-1", "key": 30, "down": True}]])
        self.assertEqual(self.panel.calls, [[{"dx": 3.0},
                                             {"button": "left", "down": True, "window": 7, "display": ":1"}]])
        self.assertEqual(out, {"state": "ready", "sent": True})

    def test_a_batch_for_one_screen_does_not_touch_the_panel_agent(self):
        out = self.s.remote_touch({"events": [{"screen": "WL-0", "fx": 0.25, "fy": 0.75}]})
        self.assertEqual(self.panel.calls, [])
        self.assertEqual(self.frametop.calls, [[{"screen": "WL-0", "fx": 0.25, "fy": 0.75}]])
        self.assertEqual(out, {"state": "ready", "sent": True})

    def test_a_frametop_agent_that_is_not_ready_holds_the_panel_events_back(self):
        # The page keeps the panel events and sends them again once Frametop is ready.
        self.frametop.state, self.frametop.sent = "starting", False
        out = self.s.remote_touch({"events": [{"dx": 1}, {"screen": "WL-0", "fx": 0.5, "fy": 0.5}]})
        self.assertEqual(out, {"state": "starting", "sent": False})
        self.assertEqual(self.panel.calls, [])

    def test_batch_limit_still_applies_before_routing(self):
        with self.assertRaises(self.s.Failure):
            self.s.remote_touch({"events": [{"screen": "WL-0", "fx": 0, "fy": 0}] * (self.s.INPUT_BATCH_LIMIT + 1)})
        with self.assertRaises(self.s.Failure):
            self.s.remote_touch({"events": "nope"})
        self.assertEqual((self.panel.calls, self.frametop.calls), ([], []))


FRAMETOP_STATUS = {
    "desktop": True,
    "remote": False,
    "why": "Turn on Frametop Remote Access to use its screens",
    "screens": [
        {"name": "WL-0", "width": 1920, "height": 1080, "x": 0, "y": 0},
        {"name": "WL-1", "width": "1280", "height": "720", "x": "1920", "y": "0"},
        {"width": 640, "height": 480},  # a disabled screen's float slot: no screen name
        {"name": "WL 2", "width": 800, "height": 600},  # not a screen name
        {"name": "WL-3", "width": "wide", "height": 600},  # not a size
        "junk",
    ],
}


class State(unittest.TestCase):
    """frametop_state: the helper's status JSON, normalised and cached for the page's poll."""

    @classmethod
    def setUpClass(cls):
        import server
        cls.s = server

    def setUp(self):
        s = self.s
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        helper = Path(self.dir.name) / "frame_frametop.py"
        helper.write_text("# stand-in helper\n")
        source_patch = mock.patch.object(s, "FRAMETOP_SOURCE", helper)
        source_patch.start()
        self.addCleanup(source_patch.stop)
        self.saved = s._frametop_saved
        self.addCleanup(setattr, s, "_frametop_saved", self.saved)
        s._frametop_saved = {"at": 0.0, "value": None}
        self.ssh = mock.Mock(return_value=json.dumps(FRAMETOP_STATUS))
        ssh_patch = mock.patch.object(s, "ssh", self.ssh)
        ssh_patch.start()
        self.addCleanup(ssh_patch.stop)

    def test_only_real_screens_survive_and_numbers_are_ints(self):
        out = self.s.frametop_state()
        self.assertEqual([screen["name"] for screen in out["screens"]], ["WL-0", "WL-1"])
        self.assertEqual(out["screens"], [
            {"name": "WL-0", "width": 1920, "height": 1080, "x": 0, "y": 0},
            {"name": "WL-1", "width": 1280, "height": 720, "x": 1920, "y": 0},
        ])
        self.assertEqual((out["desktop"], out["remote"], out["why"]),
                         (True, False, "Turn on Frametop Remote Access to use its screens"))
        self.assertEqual(self.ssh.call_count, 1)
        self.assertTrue(self.ssh.call_args.args[0].startswith("python3 -u -c "))
        self.assertEqual(self.ssh.call_args.kwargs["timeout"], 25)

    def test_the_pages_poll_is_cached_for_two_seconds(self):
        # The page polls /api/frametop; the helper runs kscreen-doctor for each answer, so
        # a second ask within 2 s is answered from the last one.
        first = self.s.frametop_state()
        second = self.s.frametop_state()
        self.assertEqual(second, first)
        self.assertEqual(self.ssh.call_count, 1)
        self.s.frametop_state(fresh=True)  # the view's own first load isn't cached
        self.assertEqual(self.ssh.call_count, 2)
        self.s._frametop_saved["at"] -= 3  # three seconds on, the cache is stale
        self.s.frametop_state()
        self.assertEqual(self.ssh.call_count, 3)

    def test_bad_answers_become_a_failure(self):
        for answer in ("not json", "[1, 2]", "null"):
            with self.subTest(answer=answer):
                self.ssh.return_value = answer
                self.s._frametop_saved = {"at": 0.0, "value": None}
                with self.assertRaises(self.s.Failure) as caught:
                    self.s.frametop_state()
                self.assertIn("gave no answer", str(caught.exception))
                self.assertEqual(caught.exception.status, 502)

    def test_an_ssh_failure_propagates(self):
        self.ssh.side_effect = self.s.Failure("The Frame isn't answering.", 503)
        with self.assertRaises(self.s.Failure) as caught:
            self.s.frametop_state()
        self.assertEqual(str(caught.exception), "The Frame isn't answering.")
        self.assertEqual(caught.exception.status, 503)

    def test_a_missing_helper_is_named(self):
        missing = Path(self.dir.name) / "not-here" / "frame_frametop.py"
        with mock.patch.object(self.s, "FRAMETOP_SOURCE", missing):
            with self.assertRaises(self.s.Failure) as caught:
                self.s.frametop_state(fresh=True)
        self.assertIn("frame_frametop.py", str(caught.exception))
        self.assertEqual(caught.exception.status, 500)


class Screens(unittest.TestCase):
    """frametop_screen: a name the page may capture and point at."""

    @classmethod
    def setUpClass(cls):
        import server
        cls.s = server

    def state(self, **changes):
        state = {"desktop": True, "remote": True, "why": "",
                 "screens": [{"name": "WL-0", "width": 1920, "height": 1080, "x": 0, "y": 0}]}
        state.update(changes)
        return state

    def screen(self, name, **changes):
        with mock.patch.object(self.s, "frametop_state", return_value=self.state(**changes)):
            return self.s.frametop_screen(name)

    def test_a_real_screen_is_returned(self):
        self.assertEqual(self.screen("WL-0"), "WL-0")

    def test_an_unknown_screen_is_a_failure(self):
        with self.assertRaises(self.s.Failure) as caught:
            self.screen("WL-1")
        self.assertIn("no screen WL-1", str(caught.exception))
        self.assertEqual(caught.exception.status, 404)

    def test_bad_names_never_ask_the_frame(self):
        for name in ("", "WL 0", "a;rm", "x" * 40):
            with self.subTest(name=name):
                with mock.patch.object(self.s, "frametop_state") as state:
                    with self.assertRaises(self.s.Failure):
                        self.s.frametop_screen(name)
                    state.assert_not_called()

    def test_a_desktop_that_is_down_carries_the_helpers_why(self):
        with self.assertRaises(self.s.Failure) as caught:
            self.screen("WL-0", desktop=False, why="Frametop isn't running on the Frame")
        self.assertEqual(str(caught.exception), "Frametop isn't running on the Frame")
        self.assertEqual(caught.exception.status, 409)

    def test_remote_access_off_is_explained(self):
        # With no why from the helper, the server has its own wording; a why wins over it.
        with self.assertRaises(self.s.Failure) as caught:
            self.screen("WL-0", remote=False)
        self.assertIn("Remote Access", str(caught.exception))
        self.assertEqual(caught.exception.status, 409)
        with self.assertRaises(self.s.Failure) as caught:
            self.screen("WL-0", remote=False, why="Frametop Remote Access is off in its settings")
        self.assertEqual(str(caught.exception), "Frametop Remote Access is off in its settings")


class Streams(unittest.TestCase):
    """stream_command(src=frametop): the helper streams one screen, not ffmpeg."""

    @classmethod
    def setUpClass(cls):
        import server
        cls.s = server

    def setUp(self):
        s = self.s
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        source = Path(self.dir.name) / "frame_frametop.py"
        source.write_text("# stand-in helper for the stream test\n")
        saved_code = s._frametop_code
        self.addCleanup(setattr, s, "_frametop_code", saved_code)
        s._frametop_code = None
        self.state = mock.patch.object(s, "frametop_state", return_value={
            "desktop": True, "remote": True, "why": "",
            "screens": [{"name": "WL-0", "width": 1920, "height": 1080, "x": 0, "y": 0}]})
        self.state.start()
        self.addCleanup(self.state.stop)
        source_patch = mock.patch.object(s, "FRAMETOP_SOURCE", source)
        source_patch.start()
        self.addCleanup(source_patch.stop)

    def test_one_screen_streams_from_the_helper(self):
        cmd = self.s.stream_command("src=frametop&screen=WL-0&h=720&fps=30")
        self.assertTrue(cmd.startswith("python3 -u -c "))
        self.assertIn("frame_frametop", cmd)
        self.assertIn("stream WL-0 --height 720 --fps 30", cmd)
        self.assertNotIn("ffmpeg", cmd)

    def test_bad_screen_names_are_refused(self):
        for name in ("a;rm", "WL 0", "", "x" * 40):
            with self.subTest(name=name):
                with self.assertRaises(self.s.Failure):
                    self.s.stream_command(f"src=frametop&screen={name}&h=720&fps=30")


class Dispatch(unittest.TestCase):
    """record(): a body naming a Frametop screen (or view) is Frametop's, the rest isn't."""

    @classmethod
    def setUpClass(cls):
        import server
        cls.s = server

    def setUp(self):
        self.frametop = mock.Mock(return_value={"state": "recording"})
        self.clips = mock.Mock()
        self.recorder = mock.Mock()
        patches = [
            mock.patch.object(self.s, "frametop_record", self.frametop),
            mock.patch.object(self.s, "_clips_here", self.clips),
            mock.patch.object(self.s, "recorder", self.recorder),
            mock.patch.object(self.s, "HEADSET_RUNTIME", False),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_a_screen_in_the_body_is_a_frametop_recording(self):
        body = {"action": "start", "screen": "WL-0"}
        self.assertEqual(self.s.record(body), {"state": "recording"})
        self.frametop.assert_called_once_with(body)
        self.recorder.start.assert_not_called()

    def test_the_view_field_also_dispatches_to_frametop(self):
        body = {"action": "stop", "view": "frametop"}
        self.s.record(body)
        self.frametop.assert_called_once_with(body)

    def test_the_plain_body_stays_with_the_headset_recorder(self):
        self.recorder.start.return_value = {"state": "recording"}
        self.assertEqual(self.s.record({"action": "start"}), {"state": "recording"})
        self.frametop.assert_not_called()
        self.recorder.start.assert_called_once_with()

    def test_a_plain_stop_finishes_a_frametop_recording(self):
        # The Frametop view's Stop needs no screen: whatever is recording is the one.
        status = mock.Mock(return_value={"state": "recording", "screen": "WL-0"})
        with mock.patch.object(self.s, "_frametop_recorder", mock.Mock(status=status)):
            self.s.record({"action": "stop"})
        self.frametop.assert_called_once_with({"action": "stop"})
        self.recorder.stop.assert_not_called()

    def test_a_plain_stop_with_no_frametop_recording_stays_with_the_headset(self):
        status = mock.Mock(return_value={"state": "idle"})
        self.recorder.stop.return_value = {"state": "idle"}
        with mock.patch.object(self.s, "_frametop_recorder", mock.Mock(status=status)):
            self.assertEqual(self.s.record({"action": "stop"}), {"state": "idle"})
        self.frametop.assert_not_called()
        self.recorder.stop.assert_called_once_with()


class Command(unittest.TestCase):
    """frametop_command: frame_frametop.py's source inlined, so the helper's stdin stays free."""

    @classmethod
    def setUpClass(cls):
        import server
        cls.s = server

    def setUp(self):
        s = self.s
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.source = Path(self.dir.name) / "frame_frametop.py"
        self.source.write_bytes(b"print('frametop stand-in')\n")
        saved_source, saved_code = s.FRAMETOP_SOURCE, s._frametop_code

        def restore():
            s.FRAMETOP_SOURCE, s._frametop_code = saved_source, saved_code
        self.addCleanup(restore)  # runs before the temp dir goes (added after it)
        s.FRAMETOP_SOURCE = self.source
        s._frametop_code = None

    def test_the_helper_travels_in_the_command(self):
        cmd = self.s.frametop_command()
        self.assertTrue(cmd.startswith("python3 -u -c "))
        self.assertIn(base64.b64encode(self.source.read_bytes()).decode(), cmd)
        self.assertIn("frame_frametop", cmd)
        self.assertNotIn(str(self.source), cmd)  # the Frame has no copy: the source is inline

    def test_the_source_is_read_once(self):
        first = self.s.frametop_command("status")
        self.source.unlink()
        self.assertEqual(self.s.frametop_command("status"), first)

    def test_arguments_are_quoted(self):
        cmd = self.s.frametop_command("stream", "WL 0", "--name", "a'b")
        self.assertIn("stream", cmd)
        self.assertIn(shlex.quote("WL 0"), cmd)
        self.assertIn(shlex.quote("a'b"), cmd)
        self.assertTrue(cmd.endswith(" " + " ".join([shlex.quote("stream"), shlex.quote("WL 0"),
                                                      shlex.quote("--name"), shlex.quote("a'b")])))

    def test_a_missing_helper_is_a_clear_failure(self):
        self.s.FRAMETOP_SOURCE = Path(self.dir.name) / "not-here" / "frame_frametop.py"
        self.s._frametop_code = None
        with self.assertRaises(self.s.Failure) as caught:
            self.s.frametop_command()
        self.assertIn("frame_frametop.py", str(caught.exception))
        self.assertEqual(caught.exception.status, 500)


class Recorder(unittest.TestCase):
    """FrametopRecorder: one Frametop screen at a time, and only when one is recording."""

    @classmethod
    def setUpClass(cls):
        import server
        cls.s = server

    def test_a_fresh_recorder_is_idle_and_refuses_to_stop(self):
        recorder = self.s.FrametopRecorder()
        self.assertEqual(recorder.status(), {"state": "idle"})
        with self.assertRaises(self.s.Failure) as caught:
            recorder.stop()
        self.assertEqual(str(caught.exception), "Not recording")
        self.assertEqual(caught.exception.status, 409)

    def test_a_second_start_is_refused(self):
        recorder = self.s.FrametopRecorder()
        recorder._state = {"state": "recording", "screen": "WL-0", "name": "2026-11-12 13-00-00",
                           "started": time.time()}
        with self.assertRaises(self.s.Failure) as caught:
            recorder.start("WL-1")
        self.assertIn("Already recording", str(caught.exception))
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(recorder.status()["state"], "recording")


class RecordingFake:
    """Stands in for frame_frametop.FakeInput: records what apply_event would send."""

    def __init__(self):
        self.calls = []

    def pointer_absolute(self, x, y):
        self.calls.append(("pointer_absolute", x, y))

    def pointer_motion(self, dx, dy):
        self.calls.append(("pointer_motion", dx, dy))

    def button(self, code, down):
        self.calls.append(("button", code, down))

    def axis(self, which, amount):
        self.calls.append(("axis", which, amount))

    def key(self, code, down):
        self.calls.append(("key", code, down))

    def text(self, message):
        self.calls.append(("text", message))


SCREENS = [
    {"name": "WL-0", "width": 1920, "height": 1080, "x": 0, "y": 0},
    {"name": "WL-1", "width": 1280, "height": 720, "x": 1920, "y": 0},
]


class Helper(unittest.TestCase):
    """ui/frame_frametop.py's pure half: no D-Bus, Wayland, ffmpeg or Frame needed."""

    @classmethod
    def setUpClass(cls):
        try:
            import frame_frametop
        except Exception as error:  # absent, or half-written by another agent
            raise unittest.SkipTest(f"ui/frame_frametop.py isn't importable ({error})")
        cls.ft = frame_frametop

    def helper(self, name):
        value = getattr(self.ft, name, None)
        if value is None:
            self.skipTest(f"frame_frametop.py has no {name}")
        return value

    def test_ascii_table_is_linux_evdev(self):
        # The helper turns typed characters into the same evdev codes frame_touch uses.
        table = getattr(self.ft, "ASCII", None)
        if table is None:
            self.skipTest("frame_frametop.py has no ASCII table")
        self.assertEqual(table["a"], (30, False))
        self.assertEqual(table["A"], (30, True))
        self.assertEqual(table["1"], (2, False))
        self.assertEqual(table["!"], (2, True))
        self.assertEqual(table["="], (13, False))
        self.assertEqual(table["+"], (13, True))
        self.assertEqual(table["q"], (16, False))       # ROW_KEYS starts the q row at 16
        self.assertEqual(table["]"], (27, False))
        self.assertEqual(table["`"], (41, False))
        self.assertEqual(table["~"], (41, True))
        self.assertEqual(table["\\"], (43, False))      # the "\\zxcvbnm,./" row starts at 43
        self.assertEqual(table["Z"], (44, True))
        self.assertEqual(table["/"], (53, False))
        self.assertEqual(table[" "], (57, False))
        self.assertEqual(table["\n"], (28, False))
        self.assertEqual(table["\t"], (15, False))

    def test_button_codes_and_fixed_point(self):
        buttons = getattr(self.ft, "BUTTONS", None)
        if buttons is not None:
            self.assertEqual(buttons, {"left": 0x110, "right": 0x111, "middle": 0x112})
        fixed = self.helper("fixed")
        self.assertEqual(fixed(1.0), 256)     # Wayland's 24.8 fixed point
        self.assertEqual(fixed(0.5), 128)
        self.assertEqual(fixed(-0.25), -64)
        self.assertEqual(fixed(0.1), 26)

    def test_fractions_and_numbers_are_clamped_and_checked(self):
        fraction, number = self.helper("fraction"), self.helper("number")
        self.assertEqual(fraction(1.7, "fx"), 1.0)
        self.assertEqual(fraction(-2, "fy"), 0.0)
        self.assertEqual(fraction(0.25, "fx"), 0.25)
        self.assertEqual(number(1e9, "dx", 2000), 2000.0)
        self.assertEqual(number(-1e9, "dx", 2000), -2000.0)
        for value in (True, "0.5", None, float("nan")):
            with self.subTest(value=value):
                with self.assertRaises(self.ft.FrametopError):
                    fraction(value, "fx")
                with self.assertRaises(self.ft.FrametopError):
                    number(value, "dx")

    def test_a_fraction_maps_onto_its_screens_pixels(self):
        apply_event = self.helper("apply_event")
        fake = RecordingFake()
        apply_event(fake, SCREENS, {"screen": "WL-1", "fx": 0.5, "fy": 0.25})
        self.assertEqual(fake.calls, [("pointer_absolute", 1920 + 0.5 * 1280, 0 + 0.25 * 720)])

    def test_a_fraction_without_a_screen_uses_the_first(self):
        apply_event = self.helper("apply_event")
        fake = RecordingFake()
        apply_event(fake, SCREENS, {"fx": 0.5, "fy": 0.5})
        self.assertEqual(fake.calls, [("pointer_absolute", 960.0, 540.0)])
        fake = RecordingFake()
        apply_event(fake, SCREENS, {"screen": "WL-0", "fx": 2, "fy": -1})  # clamped to its edges
        self.assertEqual(fake.calls, [("pointer_absolute", 1920.0, 0.0)])

    def test_bad_events_are_refused(self):
        apply_event = self.helper("apply_event")
        bad = [
            "not a dict", None,
            {"fx": 0.5},                                   # a position needs both axes
            {"screen": "WL-9", "fx": 0.5, "fy": 0.5},      # unknown screen
            {"button": "sideways"},
            {"scroll": [0]}, {"scroll": "nope"},
            {"key": 0}, {"key": 999}, {"key": True},
            {"text": 5},
            {"screen": "WL-0"},                            # names a screen, does nothing
        ]
        for event in bad:
            with self.subTest(event=event):
                with self.assertRaises(self.ft.FrametopError):
                    apply_event(RecordingFake(), SCREENS, event)

    def test_gestures_reach_the_fake_input(self):
        apply_event = self.helper("apply_event")

        def sent(event):
            fake = RecordingFake()
            apply_event(fake, SCREENS, event)
            return fake.calls

        self.assertEqual(sent({"dx": 1e9, "dy": -1e9}), [("pointer_motion", 2000.0, -2000.0)])
        self.assertEqual(sent({"button": "left", "down": False}), [("button", 0x110, False)])
        self.assertEqual(sent({"button": "middle"}), [("button", 0x112, True)])
        self.assertEqual(sent({"scroll": [0, 120]}), [("axis", 0, 120.0)])   # 0 = vertical
        self.assertEqual(sent({"scroll": [3, 0]}), [("axis", 1, 3.0)])      # 1 = horizontal
        self.assertEqual(sent({"key": 30}), [("key", 30, True)])
        self.assertEqual(sent({"text": "hi"}), [("text", "hi")])
        self.assertEqual(sent({"text": "x" * 600}), [("text", "x" * 500)])  # the helper's cap

    def test_the_servers_command_lines_reach_the_modes(self):
        # ui/server.py sends: shot <screen> / stream <screen> --height H --fps F /
        # record <screen> --name NAME, and reads the helper's stdout.
        main = self.helper("main")
        with mock.patch.object(self.ft, "ready_env", return_value={"env": 1}):
            with mock.patch.object(self.ft, "shot") as shot:
                self.assertEqual(main(["shot", "WL-0"]), 0)
                shot.assert_called_once_with("WL-0", True, {"env": 1})
                shot.reset_mock()
                self.assertEqual(main(["shot", "WL-0", "--no-cursor"]), 0)
                shot.assert_called_once_with("WL-0", False, {"env": 1})
            with mock.patch.object(self.ft, "stream") as stream:
                self.assertEqual(main(["stream", "WL-1", "--height", "720", "--fps", "30"]), 0)
                stream.assert_called_once_with("WL-1", 720, 30, {"env": 1})
            with mock.patch.object(self.ft, "record") as record:
                self.assertEqual(main(["record", "WL-1", "--name", "rec-20261112-130000"]), 0)
                record.assert_called_once_with("WL-1", "rec-20261112-130000", 30, {"env": 1})
        with self.assertRaises(self.ft.FrametopError):
            main(["record", "WL-1"])  # --name is not optional
        with self.assertRaises(self.ft.FrametopError):
            main(["nope"])

    def test_options_and_whole_numbers(self):
        parse_options, whole_number = self.helper("parse_options"), self.helper("whole_number")
        self.assertEqual(parse_options(["WL-0", "--height", "720", "--fps=30"],
                                       valued=("height", "fps")),
                         (["WL-0"], {"height": "720", "fps": "30"}))
        self.assertEqual(parse_options(["--no-cursor"], boolean=("no_cursor",)),
                         ([], {"no_cursor": True}))
        for arguments, keyword in (
            (["--bogus"], {"valued": ()}),
            (["--height"], {"valued": ("height",)}),
            (["--no-cursor=1"], {"boolean": ("no_cursor",)}),
        ):
            with self.subTest(arguments=arguments):
                with self.assertRaises(self.ft.FrametopError):
                    parse_options(arguments, **keyword)
        self.assertEqual(whole_number(None, "height", 2, 4320, 720), 720)
        self.assertEqual(whole_number("1080", "height", 2, 4320, 720), 1080)
        for value in ("wide", 1, 5000):
            with self.subTest(value=value):
                with self.assertRaises(self.ft.FrametopError):
                    whole_number(value, "height", 2, 4320, 720)

    def test_screens_parser_keeps_only_real_outputs(self):
        # kscreen-doctor marks a mode by id and points at it with currentModeId; the
        # desktop's disabled float slots (WL-2 640x480) are connected but not enabled.
        screens = self.helper("screens")
        report = {"outputs": [
            {"name": "WL-0", "connected": True, "enabled": True, "currentModeId": 1,
             "modes": [{"id": 1, "size": {"width": 1920, "height": 1080}}],
             "pos": {"x": 0, "y": 0}},
            {"name": "WL-1", "connected": True, "enabled": True, "currentModeId": "2",
             "modes": [{"id": "2", "size": {"width": 1280, "height": 720}}],
             "pos": {"x": 1920, "y": 0}},
            {"name": "WL-2", "connected": True, "enabled": False, "currentModeId": 3,
             "modes": [{"id": 3, "size": {"width": 640, "height": 480}}], "pos": {"x": 0, "y": 0}},
            {"name": "WL-3", "connected": True, "enabled": True, "currentModeId": 4,
             "modes": [{"id": 4, "size": {"width": 0, "height": 0}}]},
            "junk",
        ]}
        done = mock.Mock(returncode=0, stdout=json.dumps(report), stderr="")
        with mock.patch.object(self.ft.subprocess, "run", return_value=done) as run:
            found = screens({"DISPLAY": ":1"})
        self.assertEqual(found, SCREENS[:2])
        self.assertEqual(run.call_args.args[0], ["kscreen-doctor", "-j"])
        self.assertEqual(run.call_args.kwargs["env"], {"DISPLAY": ":1"})
        self.assertEqual(run.call_args.kwargs["timeout"], 20)

    def test_screen_lookup_lists_what_there_is(self):
        screen_or_error = self.helper("screen_or_error")
        with mock.patch.object(self.ft, "screens", return_value=SCREENS):
            self.assertEqual(screen_or_error("WL-1", {}), SCREENS[1])
            with self.assertRaises(self.ft.FrametopError) as caught:
                screen_or_error("WL-9", {})
        self.assertIn("WL-9", str(caught.exception))
        self.assertIn("WL-0, WL-1", str(caught.exception))

    def test_cache_names_are_filename_safe(self):
        pattern = getattr(self.ft, "CACHE_NAME", None)
        if pattern is None:
            self.skipTest("frame_frametop.py has no CACHE_NAME")
        # ui/frame_clips.py's recording_name() -> "rec-YYYYMMDD-HHMMSS"
        self.assertTrue(pattern.fullmatch("rec-20261112-130000"))
        for name in ("", "bad name", "../rec-1", "rec/1", "x" * 81):
            with self.subTest(name=name):
                self.assertFalse(pattern.fullmatch(name))


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(shutil.which("node"), "needs node")
class PageView(unittest.TestCase):
    """The Frametop view's page functions (tests/page/frametop_view.mjs runs the real ones from index.html)."""

    def test_frametop_view(self):
        r = subprocess.run(["node", str(ROOT / "tests" / "page" / "frametop_view.mjs")],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
