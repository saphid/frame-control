"""Experimental pulse estimate from the Frame's IR eye-tracking cameras.

Skin brightens and darkens very slightly with each heartbeat as blood volume
changes (photoplethysmography). The eye cameras film the skin around each eye
under steady IR light at about 90 frames per second, so that rhythm may be
visible in the average brightness of small patches of skin.

Capture uses SteamVR's own `eyetracking --calib` mode, which writes PNG pairs
to /tmp. Each image is reduced to a grid of patch averages the moment it is
complete, then deleted; the identified capture directory is removed on exit.
Directories not identified by the launched tool are never read or removed.
This is an experiment, not a medical measurement.
"""
from array import array
import bisect
import cmath
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import time

ET_DIR = Path("/opt/steamvr/tools/eyetracking")
ET_BIN = ET_DIR / "bin/linuxarm64/eyetracking"
ET_WEIGHTS = ET_DIR / "resources/et_dsp_20250610_03136.weights"
GRID = 16        # 16 × 16 patches of 25 × 25 pixels on the 400 × 400 image
RATE = 15.0      # analysis sample rate, Hz; the band of interest ends at 3 Hz
LOW, HIGH = 42.0, 180.0  # BPM search band
# The Frame's proximity sensor (vcnl4000) reads about 3 with nobody wearing it.
# A worn reading has not been measured yet, so the cut-off is provisional.
IIO = Path("/sys/bus/iio/devices")
WORN_MIN = 20.0
WINDOW = 15.0    # seconds per windowed estimate


# ---------------------------------------------------------------- capture ---

def grid_means(pixels, width, height, stride, channels, grid=GRID):
    """Average of channel 0 in each of grid × grid equal patches."""
    bw, bh = width // grid, height // grid
    sums = [0] * (grid * grid)
    for y in range(bh * grid):
        start = y * stride
        row = pixels[start:start + width * channels:channels]
        base = (y // bh) * grid
        for bx in range(grid):
            sums[base + bx] += sum(row[bx * bw:(bx + 1) * bw])
    area = bw * bh
    return [s / area for s in sums]


def load_grid(path):
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    image = GdkPixbuf.Pixbuf.new_from_file(str(path))
    return grid_means(image.read_pixel_bytes().get_data(), image.get_width(), image.get_height(),
                      image.get_rowstride(), image.get_n_channels())


def reduce_file(loader, path):
    """Reduce one image to its patch grid and delete it, whatever happens."""
    try:
        return loader(path)
    finally:
        os.unlink(path)


class Capture:
    """Run SteamVR's eye-camera capture and reduce frames as they arrive."""
    NAME = re.compile(r"^(left|right)_(\d+)\.png$")
    # A prefix alone is not ownership: only the launched tool's report counts.
    PREFIX = "/tmp/etcalib_"
    WRITING = re.compile(r"^Writing capture to: (.+?)\r?$", re.MULTILINE)
    REPORT_TIMEOUT = 5.0
    # About five seconds of frames (~65 MB in RAM-backed /tmp). If reduction
    # falls further behind than this, the capture stops rather than letting
    # eye images pile up.
    MAX_BACKLOG = 900

    def __init__(self, seconds, runner=subprocess.Popen, loader=load_grid, workers=3):
        self.seconds, self.runner, self.loader, self.workers = seconds, runner, loader, workers
        self.grids = {"left": {}, "right": {}}
        self.directory = None
        self.pool = None
        self.submitted = set()
        self.futures = {}
        self.before = None  # capture directories that existed before the run
        self.log = None
        self.identity = None

    def candidates(self):
        parent, stem = os.path.split(self.PREFIX)
        return {Path(entry.path) for entry in os.scandir(parent)
                if entry.name.startswith(stem) and entry.is_dir(follow_symlinks=False)}

    def run(self):
        # Ask libc to flush each output line, so the tool can identify its
        # directory before reduction starts. Never infer ownership from a new
        # name in /tmp: it may belong to another capture.
        import tempfile
        self.before = self.candidates()
        process = None
        with tempfile.TemporaryDirectory() as logs, open(Path(logs) / "capture.log", "w+") as log:
            self.log = log
            try:
                if self.workers:
                    # SteamVR pins its eye tracker to cores 0-1; decoding runs beside it.
                    import concurrent.futures
                    import multiprocessing
                    self.pool = concurrent.futures.ProcessPoolExecutor(
                        self.workers, mp_context=multiprocessing.get_context("fork"))
                try:
                    process = self.runner(["stdbuf", "-oL", "-eL", str(ET_BIN), "-b", "CDSP", "-w", str(ET_WEIGHTS), "--calib", str(self.seconds)],
                                          cwd=str(ET_BIN.parent), stdout=log, stderr=subprocess.STDOUT)
                except FileNotFoundError as error:
                    raise RuntimeError("could not start capture; check stdbuf and the SteamVR tool path") from error
                started = time.monotonic()
                self.deadline = started + self.seconds + 30
                while True:
                    finished = process.poll() is not None
                    self.adopt_reported()
                    self.reduce(final=finished)
                    if finished:
                        break
                    now = time.monotonic()
                    if not self.directory and now - started > self.REPORT_TIMEOUT:
                        raise RuntimeError("the capture did not identify its directory; "
                                           "unidentified directories are left untouched")
                    if now > self.deadline:
                        raise RuntimeError("eye-camera capture did not finish")
                    time.sleep(0.02)
                text = self.read_log()
                if process.returncode or not self.directory:
                    reason = "cameras unavailable" if "Failed to" in text else f"exit {process.returncode}"
                    if not self.directory and not process.returncode:
                        reason = "directory not identified; unidentified directories are left untouched"
                    raise RuntimeError(f"eye-camera capture failed ({reason})")
                return self.frames()
            finally:
                # Each step runs even if an earlier one failed. Only images
                # in the directory identified by our child may be removed.
                # Ctrl-C and SIGTERM (raised as KeyboardInterrupt) are held
                # until the tool ends and owned-directory cleanup is attempted.
                interrupted, failed = None, None
                for step in (lambda: self.finish(process),
                             lambda: self.pool and self.pool.shutdown(wait=True, cancel_futures=True),
                             self.adopt_reported):
                    try:
                        step()
                    except BaseException as error:
                        if isinstance(error, Exception):
                            failed = failed or error
                        else:
                            interrupted = interrupted or error
                self.log = None
                self.remove()
                if interrupted:
                    raise interrupted
                if failed:
                    raise RuntimeError(f"the eye-camera capture did not stop cleanly: {failed}")

    def finish(self, process):
        """Let the capture tool end by itself, deleting its images meanwhile.

        Never signal it: stopping the tool early leaves the headset's eye
        camera stuck streaming until the DSP service restarts (verified on the
        Frame with SIGTERM). Its run is bounded by `seconds`, so waiting is
        short. Only if it overruns by a wide margin is it killed."""
        if not process:
            return
        interrupted, failed = None, None
        while True:
            try:
                finished = process.poll() is not None
                for step in (self.adopt_reported, self.discard):
                    try:
                        step()
                    except Exception as error:
                        # Refusing another directory must not stop cleanup of
                        # the already identified one, or the natural-exit wait.
                        failed = failed or error
                if finished:
                    break
                if time.monotonic() > self.deadline:
                    process.kill()
                    process.wait()
                    raise RuntimeError("the eye-camera capture had to be killed; "
                                       "the eye cameras may need a reboot to stream again")
                time.sleep(0.05)
            except KeyboardInterrupt as error:  # keep cleaning up until it ends
                interrupted = interrupted or error
        if interrupted:
            raise interrupted
        if failed:
            raise failed

    def discard(self):
        """Delete the eye images written so far, without reading them."""
        if self.owned():
            for entry in os.scandir(self.directory):
                if self.NAME.match(entry.name) and entry.is_file(follow_symlinks=False):
                    try:
                        os.unlink(entry.path)
                    except FileNotFoundError:
                        pass

    def adopt_reported(self):
        """Accept one new directory, identified by our child's private output."""
        reports = self.WRITING.findall(self.read_log())
        if not reports:
            return
        names = {Path(report) for report in reports}
        if len(names) != 1:
            raise RuntimeError("the capture reported multiple directories; not adopting another")
        named = names.pop()
        parent, stem = os.path.split(self.PREFIX)
        if (self.before is None or named.parent != Path(parent) or
                not named.name.startswith(stem) or named in self.before):
            raise RuntimeError("the capture reported an unsafe or pre-existing directory; left untouched")
        if self.directory is None:
            try:
                info = named.lstat()
            except FileNotFoundError:
                return  # the tool may print just before creating it
            if not stat.S_ISDIR(info.st_mode):
                raise RuntimeError("the capture directory is not a real directory; left untouched")
            self.directory = named
            self.identity = (info.st_dev, info.st_ino)

    def read_log(self):
        # A separate handle avoids moving the child's shared write offset.
        # Only complete lines count as a report; output is bounded for parsing.
        if not self.log:
            return ""
        with open(self.log.name, encoding="utf-8", errors="replace") as reader:
            text = reader.read(1024 * 1024)
        return text[:text.rfind("\n") + 1]

    def owned(self):
        """Do not follow a replaced or symlinked capture directory."""
        if self.directory is None or self.identity is None:
            return False
        try:
            info = self.directory.lstat()
        except FileNotFoundError:
            return False
        if not stat.S_ISDIR(info.st_mode) or (info.st_dev, info.st_ino) != self.identity:
            raise RuntimeError("the capture directory was replaced; left untouched")
        return True

    def reduce(self, final=False):
        """Reduce and delete every complete image; an image is complete once a
        later one of the same eye exists, or the capture has ended."""
        if not self.owned():
            return
        pending = {"left": [], "right": []}
        for entry in os.scandir(self.directory):
            match = self.NAME.match(entry.name)
            if match and entry.is_file(follow_symlinks=False):
                pending[match.group(1)].append((int(match.group(2)), entry.path))
        if sum(len(files) for files in pending.values()) > self.MAX_BACKLOG:
            raise RuntimeError("eye-image processing fell behind; capture abandoned")
        for eye, files in pending.items():
            files.sort()
            ready = files if final else files[:-1]
            for index, path in ready:
                if path in self.submitted:
                    continue
                self.submitted.add(path)
                if self.pool:
                    self.futures[(eye, index)] = self.pool.submit(reduce_file, self.loader, path)
                else:
                    self.grids[eye][index] = array("f", reduce_file(self.loader, path))
        for key, future in list(self.futures.items()):
            if final or future.done():
                self.grids[key[0]][key[1]] = array("f", future.result())
                del self.futures[key]

    def frames(self):
        """[(monotonic seconds, eye, grid)] joined with the capture metadata."""
        if not self.owned():
            raise RuntimeError("the identified capture directory disappeared")
        meta = json.loads((self.directory / "meta.json").read_text())
        frames = []
        for pair in meta["frames"]:
            for eye in ("left", "right"):
                info = pair.get(eye) or {}
                match = self.NAME.match(Path(info.get("fname", "")).name)
                grid = self.grids[eye].get(int(match.group(2))) if match else None
                if info.get("valid") and grid is not None:
                    frames.append((float(info["tsMono"]), eye, grid))
        return frames

    def remove(self):
        """Remove only our identified directory; unknown captures are untouched."""
        if self.owned():
            try:
                shutil.rmtree(self.directory)
            except OSError as error:
                raise RuntimeError("could not delete eye images in " + str(self.directory)) from error


# --------------------------------------------------------------- analysis ---

def fft(values):
    """In-place iterative radix-2 FFT of a list whose length is a power of 2."""
    n = len(values)
    a = list(values)
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    size = 2
    while size <= n:
        step = cmath.exp(-2j * math.pi / size)
        half = size // 2
        for start in range(0, n, size):
            w = 1
            for k in range(start, start + half):
                t = w * a[k + half]
                a[k + half] = a[k] - t
                a[k] += t
                w *= step
        size *= 2
    return a


def resample(times, values, rate=RATE):
    """Average samples into 1/rate bins from the first sample; empty bins are
    filled from the previous bin."""
    if not times:
        return []
    start = times[0]
    count = int((times[-1] - start) * rate) + 1
    sums, counts = [0.0] * count, [0] * count
    for t, v in zip(times, values):
        i = min(int((t - start) * rate), count - 1)
        sums[i] += v
        counts[i] += 1
    out, last = [], None
    for s, c in zip(sums, counts):
        last = s / c if c else last
        out.append(last)
    first = next(v for v in out if v is not None)
    return [first if v is None else v for v in out]


def clean(signal, rate=RATE):
    """Relative change with slow drift removed; None if the patch is mostly
    blinks or eye movement. Spikes (blinks, saccades) become gaps at the
    local level rather than clipped steps, which would add false rhythm."""
    mean = sum(signal) / len(signal)
    x = [v / mean - 1 for v in signal]
    half = int(rate)  # 2-second centred moving median removes drift and blinks
    trend = []
    for i in range(len(x)):
        chunk = sorted(x[max(0, i - half):i + half + 1])
        trend.append(chunk[len(chunk) // 2])
    residual = [v - m for v, m in zip(x, trend)]
    mad = sorted(abs(v) for v in residual)[len(residual) // 2] or 1e-9
    limit = 4 * 1.4826 * mad
    spikes = sum(1 for v in residual if abs(v) > limit)
    if spikes > 0.05 * len(residual):
        return None
    return [v if abs(v) <= limit else 0.0 for v in residual]


def spectrum(signal, rate=RATE):
    """[(bpm, power)] within the search band, Hann-windowed and zero-padded."""
    n = len(signal)
    size = 1
    while size < max(n * 4, 256):
        size *= 2
    window = [0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1)) for i in range(n)] if n > 1 else [1.0]
    padded = [s * w for s, w in zip(signal, window)] + [0.0] * (size - n)
    result = fft(padded)
    out = []
    for k in range(size // 2):
        bpm = k * rate / size * 60
        if LOW <= bpm <= HIGH:
            out.append((bpm, abs(result[k]) ** 2))
    return out


def peak(spec):
    """Peak BPM with parabolic interpolation between spectral bins."""
    i = max(range(len(spec)), key=lambda k: spec[k][1])
    if 0 < i < len(spec) - 1:
        a, b, c = spec[i - 1][1], spec[i][1], spec[i + 1][1]
        denominator = a - 2 * b + c
        offset = 0.5 * (a - c) / denominator if denominator else 0.0
        return spec[i][0] + offset * (spec[1][0] - spec[0][0])
    return spec[i][0]


def snr(spec, bpm, width=4.0):
    """Power near the pulse and its first harmonic against the rest of the band."""
    near = sum(p for f, p in spec if abs(f - bpm) <= width or abs(f - 2 * bpm) <= width)
    rest = sum(p for f, p in spec) - near
    if near <= 0:
        return 0.0
    return near / rest if rest > 0 else float("inf")


def normalised(spec):
    total = sum(p for _, p in spec) or 1.0
    return [p / total for _, p in spec]


def usable(values):
    """Patches that are neither dark nor saturated for the whole recording."""
    mean = sum(values) / len(values)
    return 8 <= mean <= 245


def estimate(times, patches, rate=RATE, share=0.2, window=WINDOW):
    """Estimate pulse from patch brightness traces.

    times: monotonic seconds per frame. patches: {name: [brightness per frame]}.
    Selects the share of usable patches with the clearest periodic signal,
    combines their spectra and reports the overall and windowed estimates.
    """
    cleaned = {}
    for name, values in patches.items():
        if usable(values):
            signal = clean(resample(times, values, rate), rate)
            if signal is not None and any(signal):  # flat patches carry no rhythm
                cleaned[name] = signal
    if not cleaned or len(next(iter(cleaned.values()))) < rate * 8:
        raise ValueError("need at least 8 seconds of usable eye-camera frames")
    quality = []
    for name, signal in cleaned.items():
        spec = spectrum(signal, rate)
        own = peak(spec)
        quality.append((snr(spec, own), name, own, spec))
    quality.sort(reverse=True)
    chosen = quality[:max(4, int(len(quality) * share))]
    combined = [sum(values) for values in zip(*(normalised(spec) for _, _, _, spec in chosen))]
    bins = [f for f, _ in chosen[0][3]]
    bpm = peak(list(zip(bins, combined)))
    top = chosen[:8]
    agree = sum(1 for _, _, own, _ in top if abs(own - bpm) <= 5) / len(top)
    series = []
    samples = int(window * rate)
    length = len(next(iter(cleaned.values())))
    for end in range(samples, length + 1, int(rate)):
        specs = [spectrum(cleaned[name][end - samples:end], rate) for _, name, _, _ in chosen]
        total = [sum(values) for values in zip(*(normalised(s) for s in specs))]
        window_bins = [f for f, _ in specs[0]]
        series.append((times[0] + end / rate, peak(list(zip(window_bins, total)))))
    return {
        "bpm": bpm,
        "agreement": agree,
        "patches": len(chosen),
        "usable": len(cleaned),
        "snr": snr(list(zip(bins, combined)), bpm),
        "series": series,
    }


def analyse(frames):
    """Estimate from Capture.frames(); both eyes' patches are analysed together
    on a shared time base, each sample taken from that eye's nearest frame."""
    times = sorted({t for t, _, _ in frames})
    patches = {}
    for eye in ("left", "right"):
        eye_frames = sorted((t, grid) for t, e, grid in frames if e == eye)
        if not eye_frames:
            continue
        eye_times = [t for t, _ in eye_frames]
        nearest = []
        for t in times:
            i = bisect.bisect_left(eye_times, t)
            if i == len(eye_times) or (i > 0 and t - eye_times[i - 1] <= eye_times[i] - t):
                i -= 1
            nearest.append(i)
        for k in range(len(eye_frames[0][1])):
            patches[f"{eye}{k}"] = [eye_frames[i][1][k] for i in nearest]
    return estimate(times, patches)


def proximity(root=None):
    """The headset's proximity reading, or None if it can't be read."""
    try:
        for device in sorted(Path(root or IIO).glob("iio:device*")):
            if (device / "name").read_text().strip() == "vcnl4000":
                return float((device / "in_proximity_raw").read_text())
    except (OSError, ValueError):
        pass
    return None


def worn(reading):
    """False only when the sensor says the headset is not on a face."""
    return reading is None or reading >= WORN_MIN


def reliable(result):
    """Whether the estimate is clear enough to show as a reading. Thresholds
    are provisional until checked against a reference on a real wearer."""
    return result["agreement"] >= 0.75 and result["snr"] >= 0.5
