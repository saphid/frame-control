"""Eye-camera pulse estimate and the heart-rate comparison tool; no headset needed."""
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import random
import socket
import struct
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pulse = load("pulse", "frame/tracking/pulse.py")
check = load("heart_check", "scripts/heart-check.py")


def synthetic(bpm, pulsing, seconds=40, fps=30, patches=48, noise=0.004, seed=7):
    """Patch brightness with a faint pulse in `pulsing` patches, plus sensor
    noise, slow drift, blinks in some patches and eye movement in others."""
    rng = random.Random(seed)
    times = [i / fps for i in range(seconds * fps)]
    values = {}
    for k in range(patches):
        base, amplitude, trace = 40 + k, 0.003 if k < pulsing else 0.0, []
        for t in times:
            v = base * (1 + amplitude * math.sin(2 * math.pi * bpm / 60 * t)
                        + noise * rng.gauss(0, 1) + 0.02 * math.sin(0.1 * t + k))
            if k % 8 == 7 and int(t * 10) % 47 == 0:
                v *= 0.5   # blink
            if k % 8 == 6 and int(t * 10) % 23 == 0:
                v *= 1.3   # frequent eye movement
            trace.append(v)
        values[k] = trace
    return times, values


class Estimate(unittest.TestCase):
    def test_finds_pulse(self):
        for bpm in (58, 72, 115):
            with self.subTest(bpm=bpm):
                result = pulse.estimate(*synthetic(bpm, 16))
                self.assertAlmostEqual(result["bpm"], bpm, delta=1.5)
                self.assertTrue(pulse.reliable(result))
                self.assertTrue(all(abs(b - bpm) <= 2 for _, b in result["series"]))

    def test_noise_and_blinks_are_not_a_pulse(self):
        result = pulse.estimate(*synthetic(72, 0))
        self.assertFalse(pulse.reliable(result))

    def test_frequent_spike_patches_are_dropped(self):
        times, values = synthetic(72, 16)
        result = pulse.estimate(times, values)
        self.assertLess(result["usable"], len(values))

    def test_needs_enough_frames(self):
        with self.assertRaises(ValueError):
            pulse.estimate(*synthetic(72, 16, seconds=5))
        times, values = synthetic(72, 16)
        with self.assertRaises(ValueError):
            pulse.estimate(times, {k: [0.0] * len(times) for k in values})  # all dark

    def test_series_times(self):
        times, values = synthetic(72, 16, seconds=20)
        series = pulse.estimate(times, values)["series"]
        self.assertAlmostEqual(series[0][0], pulse.WINDOW, delta=0.1)
        self.assertEqual(len(series), 20 - int(pulse.WINDOW) + 1)

    def test_flat_patches_do_not_rank_first(self):
        times, values = synthetic(72, 16)
        values["flat"] = [100.0] * len(times)
        result = pulse.estimate(times, values)
        self.assertAlmostEqual(result["bpm"], 72, delta=1.5)
        self.assertEqual(pulse.snr([(60.0, 0.0), (61.0, 0.0)], 60), 0.0)

    def test_analyse_uses_nearest_frame(self):
        times, values = synthetic(72, 4, patches=4, seconds=10)
        # Right-eye frames 1 ms before each left frame: nearest is that frame.
        frames = [(t, "left", [values[k][i] for k in range(4)]) for i, t in enumerate(times)]
        frames += [(t - 0.001, "right", [float(i)] * 4) for i, t in enumerate(times)]
        seen = {}
        original = pulse.estimate
        with patch.object(pulse, "estimate", lambda t, p: seen.update(p) or original(t, p)):
            pulse.analyse(frames)
        self.assertEqual(seen["right0"][:5], [0.0, 0.0, 1.0, 1.0, 2.0])

    def test_fft_matches_dft(self):
        signal = [math.sin(i) + (i % 3) for i in range(16)]
        fast = pulse.fft(signal)
        for k in range(16):
            slow = sum(signal[n] * complex(math.cos(2 * math.pi * k * n / 16), -math.sin(2 * math.pi * k * n / 16))
                       for n in range(16))
            self.assertAlmostEqual(abs(fast[k] - slow), 0, places=9)

    def test_grid_means(self):
        # 4 × 4 image in RGB with padding: left half 10, right half 30 (channel 0).
        width, height, channels, stride = 4, 4, 3, 16
        pixels = bytearray(stride * height)
        for y in range(height):
            for x in range(width):
                pixels[y * stride + x * channels] = 10 if x < 2 else 30
                pixels[y * stride + x * channels + 1] = 255  # other channels ignored
        self.assertEqual(pulse.grid_means(bytes(pixels), width, height, stride, channels, grid=2),
                         [10, 30, 10, 30])

    def test_analyse_combines_both_eyes(self):
        times, values = synthetic(80, 16, patches=16)
        frames = []
        for i, t in enumerate(times):
            frames.append((t, "left", [values[k][i] for k in range(16)]))
            frames.append((t + 0.001, "right", [values[k][i] for k in range(16)]))
        result = pulse.analyse(frames)
        self.assertAlmostEqual(result["bpm"], 80, delta=1.5)
        self.assertEqual(result["usable"] % 2, 0)


class FakeCaptureTool:
    """Stands in for `eyetracking --calib`: writes PNG names over a few polls."""
    def __init__(self, directory, frames=6, fail=False):
        self.directory, self.frames, self.fail = Path(directory), frames, fail
        self.polls = 0
        self.returncode = None
        self.stdout = None
        self.announce = None  # a different directory to report, if set

    def __call__(self, command, cwd, stdout, stderr):
        self.command = command
        self.stdout = stdout
        if self.fail:
            stdout.write("Failed to initialize cameras\n")
            stdout.flush()
            self.returncode = 1
            return self
        self.directory.mkdir()
        # Capture now requests line buffering with stdbuf before it reads PNGs.
        stdout.write(f"Writing capture to: {self.announce or self.directory}\n")
        stdout.flush()
        return self

    def poll(self):
        if self.returncode is not None:
            return self.returncode
        if self.polls < self.frames:
            for eye in ("left", "right"):
                (self.directory / f"{eye}_{self.polls}.png").write_bytes(b"png")
            self.polls += 1
            return None
        meta = {"frames": [{eye: {"fname": str(self.directory / f"{eye}_{i}.png"), "frameNum": i + 10,
                                  "tsMono": 100 + i / 90, "valid": i != 2} for eye in ("left", "right")}
                           for i in range(self.frames)]}
        (self.directory / "meta.json").write_text(json.dumps(meta))
        self.stdout.write("Captured images\n")
        self.stdout.flush()
        self.returncode = 0
        return 0

    def terminate(self):
        raise AssertionError("the capture tool must never be signalled")

    kill = terminate

    def wait(self, timeout=None):
        return self.returncode


class WornCheck(unittest.TestCase):
    def sensor(self, name, raw):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        device = root / "iio:device2"
        device.mkdir()
        (device / "name").write_text(name + "\n")
        (device / "in_proximity_raw").write_text(raw + "\n")
        return root

    @unittest.skipIf(os.name == "nt", "Linux sysfs device names contain a colon")
    def test_reads_the_proximity_sensor(self):
        self.assertEqual(pulse.proximity(self.sensor("vcnl4000", "3.250000000")), 3.25)

    @unittest.skipIf(os.name == "nt", "Linux sysfs device names contain a colon")
    def test_unreadable_sensor_does_not_block(self):
        self.assertIsNone(pulse.proximity(self.sensor("other", "9")))
        self.assertIsNone(pulse.proximity(self.sensor("vcnl4000", "junk")))
        self.assertIsNone(pulse.proximity(Path("/nonexistent")))
        self.assertTrue(pulse.worn(None))

    def test_low_reading_means_unworn(self):
        self.assertFalse(pulse.worn(3.1))
        self.assertTrue(pulse.worn(pulse.WORN_MIN))


class CaptureLifecycle(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.directory = self.root / "etcalib_test"
        (self.root / "etcalib_older").mkdir()  # an earlier capture is not ours
        self.loaded = []

    def tearDown(self):
        import shutil
        shutil.rmtree(self.root, ignore_errors=True)

    def loader(self, path):
        self.loaded.append(Path(path).name)
        self.assertTrue(Path(path).exists())
        return [float(len(self.loaded))]

    def capture(self, tool):
        class TestCapture(pulse.Capture):
            # A temporary directory stands in for /tmp/etcalib_*.
            PREFIX = str(self.root / "etcalib_")
        capture = TestCapture(20, runner=tool, loader=self.loader, workers=0)
        with patch.object(pulse.time, "sleep", lambda s: None):
            return capture, capture.run()

    def test_reduces_deletes_and_joins_metadata(self):
        tool = FakeCaptureTool(self.directory)
        capture, frames = self.capture(tool)
        self.assertEqual(sorted(self.loaded), sorted(f"{e}_{i}.png" for e in ("left", "right") for i in range(6)))
        self.assertFalse(self.directory.exists())  # images and metadata removed
        self.assertTrue((self.root / "etcalib_older").exists())
        self.assertEqual(len(frames), 10)          # frame 2 invalid in both eyes
        self.assertEqual(tool.command[-2:], ["--calib", "20"])
        self.assertEqual(tool.command[:3], ["stdbuf", "-oL", "-eL"])
        self.assertTrue(all(isinstance(t, float) and eye in ("left", "right") for t, eye, _ in frames))

    def test_camera_failure(self):
        tool = FakeCaptureTool(self.directory, fail=True)
        with self.assertRaises(RuntimeError) as raised:
            self.capture(tool)
        self.assertIn("cameras unavailable", str(raised.exception))

    def test_missing_capture_command_reports_required_tools(self):
        def missing(*args, **kwargs):
            raise FileNotFoundError("not installed")
        with self.assertRaisesRegex(RuntimeError, "check stdbuf"):
            self.capture(missing)
        self.assertEqual(self.loaded, [])
        self.assertTrue((self.root / "etcalib_older").exists())

    def test_backlog_abandons_capture_and_removes_images(self):
        class Stalled(FakeCaptureTool):
            def poll(self):
                if self.polls > 8:
                    self.returncode = 0  # the bounded run ends by itself
                    return 0
                for i in range(20):
                    for eye in ("left", "right"):
                        (self.directory / f"{eye}_{self.polls * 20 + i}.png").write_bytes(b"png")
                self.polls += 1
                return None
        tool = Stalled(self.directory)
        class TestCapture(pulse.Capture):
            PREFIX = str(self.root / "etcalib_")
            MAX_BACKLOG = 50
        capture = TestCapture(20, runner=tool, loader=self.loader, workers=0)
        capture.reduce = lambda final=False, original=capture.reduce: (
            original(final) if tool.polls > 3 else None)  # reduction stalls
        with patch.object(pulse.time, "sleep", lambda s: None), self.assertRaises(RuntimeError) as raised:
            capture.run()
        self.assertIn("fell behind", str(raised.exception))
        self.assertEqual(tool.returncode, 0)         # left to end by itself, never signalled
        self.assertFalse(self.directory.exists())    # no image left behind

    def test_competing_capture_is_not_read_or_deleted(self):
        foreign = self.root / "etcalib_foreign"
        sentinel = b"another capture's private image"
        class Racing(FakeCaptureTool):
            def poll(self):
                if self.polls == 2:
                    foreign.mkdir()
                    (foreign / "left_999.png").write_bytes(sentinel)
                    (foreign / "notes.txt").write_text("keep this")
                return super().poll()
        tool = Racing(self.directory)
        self.capture(tool)
        self.assertFalse(self.directory.exists())
        self.assertEqual((foreign / "left_999.png").read_bytes(), sentinel)
        self.assertEqual((foreign / "notes.txt").read_text(), "keep this")
        self.assertNotIn("left_999.png", self.loaded)
        self.assertTrue((self.root / "etcalib_older").exists())

    def test_reported_preexisting_directory_is_not_read_or_removed(self):
        tool = FakeCaptureTool(self.directory)
        tool.announce = self.root / "etcalib_reported"
        tool.announce.mkdir()
        (tool.announce / "left_0.png").write_bytes(b"png")
        with self.assertRaises(RuntimeError) as raised:
            self.capture(tool)
        self.assertEqual((tool.announce / "left_0.png").read_bytes(), b"png")
        self.assertTrue(self.directory.exists())  # never identified by the child
        self.assertEqual(self.loaded, [])
        self.assertEqual(tool.returncode, 0)  # refusal still waits for natural exit
        self.assertIn("pre-existing", str(raised.exception))

    def test_foreign_directory_before_the_first_report_is_not_adopted(self):
        foreign = self.root / "etcalib_foreign"
        class LateStart(FakeCaptureTool):
            def __call__(self, command, cwd, stdout, stderr):
                foreign.mkdir()
                (foreign / "left_999.png").write_bytes(b"private")
                return super().__call__(command, cwd, stdout, stderr)
        self.capture(LateStart(self.directory))
        self.assertEqual((foreign / "left_999.png").read_bytes(), b"private")
        self.assertNotIn("left_999.png", self.loaded)
        self.assertFalse(self.directory.exists())

    def test_conflicting_report_does_not_stop_owned_cleanup_while_waiting(self):
        foreign = self.root / "etcalib_foreign"
        class Conflicting(FakeCaptureTool):
            maximum = 0
            def poll(self):
                self.maximum = max(self.maximum, len(list(self.directory.glob("*.png"))))
                if self.polls == 2:
                    foreign.mkdir()
                    (foreign / "left_999.png").write_bytes(b"private")
                    self.stdout.write(f"Writing capture to: {foreign}\n")
                    self.stdout.flush()
                return super().poll()
        tool = Conflicting(self.directory)
        with self.assertRaisesRegex(RuntimeError, "multiple directories"):
            self.capture(tool)
        self.assertLessEqual(tool.maximum, 4)
        self.assertEqual(tool.returncode, 0)
        self.assertFalse(self.directory.exists())
        self.assertEqual((foreign / "left_999.png").read_bytes(), b"private")
        self.assertNotIn("left_999.png", self.loaded)

    def test_image_symlink_is_not_decoded_or_followed(self):
        foreign = self.root / "private.png"
        foreign.write_bytes(b"private")
        class Linked(FakeCaptureTool):
            def __call__(self, command, cwd, stdout, stderr):
                result = super().__call__(command, cwd, stdout, stderr)
                try:
                    (self.directory / "left_999.png").symlink_to(foreign)
                except OSError as error:
                    raise unittest.SkipTest("symlinks unavailable: " + str(error))
                return result
        self.capture(Linked(self.directory))
        self.assertNotIn("left_999.png", self.loaded)
        self.assertEqual(foreign.read_bytes(), b"private")

    def test_no_report_never_guesses_a_directory(self):
        class Silent(FakeCaptureTool):
            def __call__(self, command, cwd, stdout, stderr):
                result = super().__call__(command, cwd, stdout, stderr)
                stdout.seek(0)
                stdout.truncate()
                stdout.flush()
                return result
        tool = Silent(self.directory)
        with self.assertRaisesRegex(RuntimeError, "directory not identified"):
            self.capture(tool)
        self.assertEqual(self.loaded, [])
        self.assertTrue((self.directory / "left_0.png").exists())
        self.assertEqual(tool.returncode, 0)

    def test_delayed_report_allows_cleanup_without_guessing(self):
        class Delayed(FakeCaptureTool):
            def __call__(self, command, cwd, stdout, stderr):
                result = super().__call__(command, cwd, stdout, stderr)
                stdout.seek(0)
                stdout.truncate()
                stdout.flush()
                return result
            def poll(self):
                result = super().poll()
                if result is not None:
                    self.stdout.write(f"Writing capture to: {self.directory}\n")
                    self.stdout.flush()
                return result
        tool = Delayed(self.directory)
        clock = iter(range(1000))
        with patch.object(pulse.time, "monotonic", lambda: next(clock)), \
                self.assertRaisesRegex(RuntimeError, "did not identify"):
            self.capture(tool)
        self.assertEqual(self.loaded, [])
        self.assertEqual(tool.returncode, 0)
        self.assertFalse(self.directory.exists())

    def test_interrupt_during_cleanup_still_removes_images(self):
        class Stubborn(FakeCaptureTool):
            interrupts = 0
            def poll(self):
                if self.polls == 2 and self.interrupts < 2:
                    self.interrupts += 1
                    raise KeyboardInterrupt  # Ctrl-C mid-capture, and again while waiting
                return super().poll()
        tool = Stubborn(self.directory)
        with self.assertRaises(KeyboardInterrupt):
            self.capture(tool)
        self.assertEqual(tool.returncode, 0)         # still let finish, never signalled
        self.assertFalse(self.directory.exists())

    def test_overrunning_tool_is_killed_as_a_last_resort(self):
        class Hung(FakeCaptureTool):
            killed = False
            def poll(self):
                (self.directory / "left_0.png").write_bytes(b"png")
                return None if not self.killed else -9
            def kill(self):
                self.killed = True
        tool = Hung(self.directory)
        clock = iter(range(0, 10000, 20))
        with patch.object(pulse.time, "monotonic", lambda: next(clock)), \
                self.assertRaises(RuntimeError) as raised:
            self.capture(tool)
        self.assertIn("may need a reboot", str(raised.exception))
        self.assertTrue(tool.killed)
        self.assertFalse(self.directory.exists())

    def test_cleanup_failure_is_reported(self):
        capture = pulse.Capture(20)
        capture.PREFIX = str(self.root / "etcalib_")
        self.directory.mkdir()
        capture.directory = self.directory
        info = self.directory.stat()
        capture.identity = (info.st_dev, info.st_ino)
        with patch.object(pulse.shutil, "rmtree", side_effect=OSError("busy")), self.assertRaises(RuntimeError) as raised:
            capture.remove()
        self.assertIn("could not delete eye images", str(raised.exception))

    def test_late_unidentified_directory_is_not_removed(self):
        capture = pulse.Capture(20)
        capture.PREFIX = str(self.root / "etcalib_")
        capture.before = capture.candidates()
        late = self.root / "etcalib_late"
        late.mkdir()
        (late / "left_0.png").write_bytes(b"png")
        capture.remove()
        self.assertEqual((late / "left_0.png").read_bytes(), b"png")
        self.assertTrue((self.root / "etcalib_older").exists())

    def test_never_adopts_directories_without_a_baseline(self):
        capture = pulse.Capture(20)
        capture.PREFIX = str(self.root / "etcalib_")
        capture.remove()
        self.assertTrue((self.root / "etcalib_older").exists())

    def test_only_removes_capture_directories(self):
        capture = pulse.Capture(20)
        capture.directory = self.root
        capture.remove()
        self.assertTrue(self.root.exists())

    def test_replaced_owned_directory_is_not_read_or_removed(self):
        class Replacing(FakeCaptureTool):
            def poll(self):
                if self.polls == 2:
                    self.directory.rename(self.directory.with_name("saved"))
                    self.directory.mkdir()
                    (self.directory / "left_999.png").write_bytes(b"foreign")
                return super().poll()
        tool = Replacing(self.directory)
        with self.assertRaisesRegex(RuntimeError, "replaced"):
            self.capture(tool)
        self.assertNotIn("left_999.png", self.loaded)
        self.assertEqual((self.directory / "left_999.png").read_bytes(), b"foreign")
        self.assertEqual(tool.returncode, 0)


class HeartCheck(unittest.TestCase):
    def write(self, name, text):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / name
        path.write_text(text)
        return path

    def test_osc_round_trip(self):
        tracking = load("tracking", "frame/tracking/tracking.py")
        self.assertEqual(check.parse_osc(tracking.osc_message("/avatar/parameters/HeartRate", [72])),
                         ("/avatar/parameters/HeartRate", [72]))
        address, values = check.parse_osc(tracking.osc_message("/x", [1.5, -2.0]))
        self.assertEqual((address, values), ("/x", [1.5, -2.0]))
        with self.assertRaises(ValueError):
            check.parse_osc(b"/x\0\0,s\0\0abc\0")

    def test_listen_records_readings(self):
        tracking = load("tracking", "frame/tracking/tracking.py")
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "ours.csv"
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            import threading
            def send():
                import time
                time.sleep(0.3)
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                    sender.sendto(tracking.osc_message(check.ADDRESS, [72]), ("127.0.0.1", port))
                    sender.sendto(tracking.osc_message("/other", [1]), ("127.0.0.1", port))
            threading.Thread(target=send).start()
            shown = io.StringIO()
            count = check.listen(port, check.ADDRESS, str(out), 1.5, stream=shown)
            self.assertEqual(count, 1)
            self.assertIn("72 bpm", shown.getvalue())
            self.assertEqual(out.read_text().splitlines()[1].split(",")[1], "72")
            if os.name != "nt":  # Windows does not implement POSIX permission bits.
                self.assertEqual(out.stat().st_mode & 0o777, 0o600)

    def test_compare_finds_lag_and_contact_loss(self):
        reference = [(1000.0 + i, 60 + i, 6) for i in range(40)] + [(1040.0 + i, 150, 4) for i in range(5)]
        ours = [(1002.0 + i, 60 + i) for i in range(40)]  # 2 s late, nothing during contact loss
        ref = self.write("ref.csv", "unix_seconds,bpm,flags\n" + "".join(f"{t},{b},{f}\n" for t, b, f in reference))
        mine = self.write("ours.csv", "unix_seconds,bpm\n" + "".join(f"{t},{b}\n" for t, b in ours))
        result = check.compare(check.read_csv(mine), check.read_any(ref))
        self.assertEqual(result["lag_seconds"], 2.0)
        self.assertEqual(result["mean_abs_error"], 0)
        self.assertEqual(result["shown_during_no_contact"], 0)
        self.assertTrue(check.report(result, 5, stream=io.StringIO()))
        # A stale reading sent during contact loss fails the check.
        stale = check.read_csv(mine) + [(1043.0, 99)]
        result = check.compare(stale, check.read_any(ref))
        self.assertEqual(result["shown_during_no_contact"], 1)
        self.assertFalse(check.report(result, 5, stream=io.StringIO()))

    def test_compare_against_apple_health_export(self):
        records = "".join(
            f'<Record type="HKQuantityTypeIdentifierHeartRate" unit="count/min" '
            f'startDate="2026-09-29 12:00:{s:02d} +1000" endDate="2026-09-29 12:00:{s:02d} +1000" value="{70 + s % 3}"/>'
            for s in range(0, 60, 5))
        other = '<Record type="HKQuantityTypeIdentifierStepCount" startDate="2026-09-29 12:00:00 +1000" value="9"/>'
        xml = f'<?xml version="1.0"?><HealthData>{other}{records}</HealthData>'
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "export.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("apple_health_export/export.xml", xml)
            start = check.parse_time("2026-09-29 12:00:00 +1000")
            samples = check.read_any(archive, start - 60, start + 120)
            self.assertEqual(len(samples), 12)
            self.assertEqual(samples[0], (start, 70))
            ours = [(start + i + 1.0, 71) for i in range(60)]
            result = check.compare(ours, samples)
            self.assertLessEqual(result["mean_abs_error"], 1)

    def test_unusual_flags_and_missing_export(self):
        path = self.write("ref.csv", "time,bpm,flags\n1000,70,6.0\n1001,71,yes\n1002,72,4\n")
        self.assertEqual(check.read_csv(path), [(1000.0, 70), (1001.0, 71), (1002.0, None)])
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "other.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("notes.txt", "x")
            with self.assertRaises(ValueError):
                check.read_any(archive, 0, 1)

    def test_compare_reports_bad_input_without_traceback(self):
        good = self.write("ref.csv", "1000,70\n")
        shown = io.StringIO()
        with patch("sys.stdout", shown):
            self.assertEqual(check.main(["compare", str(good.parent / "missing.csv"), str(good)]), 1)
            self.assertEqual(check.main(["compare", str(self.write("ours.csv", "1000,inf\n1001,70\n")),
                                         str(self.write("bad.xml", "<not closed"))]), 1)
        self.assertEqual(shown.getvalue().count("Could not compare"), 2)

    def test_health_records_with_non_finite_values_are_skipped(self):
        record = '<Record type="HKQuantityTypeIdentifierHeartRate" startDate="2026-09-29 12:00:00 +1000" value="%s"/>'
        path = self.write("export.xml", "<HealthData>" + record % "inf" + record % "72" + "</HealthData>")
        start = check.parse_time("2026-09-29 12:00:00 +1000")
        self.assertEqual(check.read_health(path, start - 1, start + 1), [(start, 72)])

    def test_time_formats(self):
        self.assertEqual(check.parse_time("1700000000.5"), 1700000000.5)
        self.assertEqual(check.parse_time("2023-11-14T22:13:20Z"), 1700000000)
        self.assertEqual(check.parse_time("2023-11-15 08:13:20 +1000"), 1700000000)
        with self.assertRaises(ValueError):
            check.parse_time("yesterday")


if __name__ == "__main__":
    unittest.main()
