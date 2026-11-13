# Read-only power and heat measurements

Issue [#52](https://github.com/saphid/frame-control/issues/52) starts with
measurement. `scripts/frame-power-sample.sh` is a bounded, on-demand sampler
over the existing `ssh frame` alias. It needs Python 3 on both computers and
an already paired, awake, reachable Frame. It uses strict SSH host-key checking
and batch mode; it never pairs, prompts for a password or changes SSH security.

```sh
# Twelve samples, five seconds apart (about 55 seconds), JSON report:
scripts/frame-power-sample.sh > power.json

# Five-minute observation: samples at 0, 5, ... 300 seconds:
scripts/frame-power-sample.sh --count 61 --interval 5 > baseline.json

# Long-form CSV samples; JSON summary goes separately to stderr:
scripts/frame-power-sample.sh --count 12 --interval 5 --csv > power.csv 2> summary.json
```

Count is limited to 1–720; interval to finite values from 1–60 seconds. These
are target start-to-start intervals, not guarantees: read latency can delay a
sample. Wall-clock `time` and monotonic `elapsedSeconds` record actual timing.
The first sample has no CPU utilization: two valid `/proc/stat` observations
are required. CPU utilization then covers the interval between observations,
averaged across the machine, rather than the utilization of one process.

## Start, stop and open an accessible report

From a source checkout with Python 3 and your already trusted `ssh frame`
connection, start a local observation:

```sh
scripts/frame-power-sample.sh --count 12 --interval 5 --html power-report.html
```

Progress is printed on your computer as each sample arrives. Wait for completion,
or press **Ctrl+C once** to stop local collection and save the samples already
received. Open `power-report.html` in your browser using its Open File command.
The file is self-contained and works offline: no server, scripts, external
resources, account or upload. It includes a table with named metrics, source
paths, units, minimum/mean/maximum/last values, and available/unknown counts.
Keyboard users can focus the table region to scroll through its columns.
Charging states and entirely unavailable sensor families remain explicit.
Use **Download JSON samples and summary** or **Download CSV samples** to save
raw measurements. The HTML also embeds those measurements; review it before
sharing. No automatic browser launch occurs.

HTML sessions are limited to `count × interval <= 600` seconds, with a 30-second
transport allowance and at most twelve seconds of local child/pipe cleanup. The default
12 samples at five-second intervals take about 55 seconds. Existing output files
are never overwritten; choose a new filename for each run. `--html` cannot be
combined with `--csv`. The desktop flow below uses the same sampler and renderer.

Stop, timeout, SSH failure or a smoke-test lock marks the report incomplete;
earlier received samples remain downloadable. Exit status is 75 for incomplete
reports, 0 for completion. A connection that cannot start may instead return 1
without an HTML file. Empty reports clearly show zero samples, not a successful
measurement. If saving the file fails, received JSON is printed on stdout as a
recovery path. Do not treat a partial report as a full baseline.

Stopping terminates only this command's local SSH child. It sends no remote
process-control command. The bounded remote Python reader exits when it next
writes to the closed connection (normally at the next sample, up to one interval
later); it can still read sensors before discovering the disconnect. Stop is
not an immediate headset-side cancellation guarantee. The reader still checks
the smoke-test lock before every sample. No lock is acquired or removed by this
flow, and no power, thermal, service, password or security controls are exposed.

## Desktop Tools → Power & heat report

In the packaged desktop app, connect to an already paired Frame, open **Tools →
Power & heat report**, choose **1 minute** (12 samples) or **5 minutes** (60 samples),
and select **Start observation**. Samples arrive every five seconds, starting at
zero (about 55 or 295 seconds total). Progress shows received samples and the
original headset alias. There is at most one observation per local app server;
viewing progress never starts another SSH connection. No terminal, checkout,
extra dependency or password is needed.

Use **Stop and keep samples** to end local collection. Disconnect, timeout,
app shutdown or switching to another headset also ends collection. Switching
network addresses for the same headset does not retarget an existing observation:
it keeps its captured SSH route and may finish incomplete if that route fails.
As with the CLI, only the owned local SSH child is terminated. The remote reader
is bounded and discovers a closed connection on its next write. Desktop sessions
have a 30-second transport allowance and bounded child cleanup. Stream lines are
limited to 262,144 characters, sample events to the requested count, and the receive queue
to count + 2 events; desktop SSH stderr is discarded rather than stored unbounded.
The existing smoke lock is checked locally before start and remotely before each
sample; this feature never creates, bypasses or removes that lock.

**Download HTML report**, **Download JSON** and **Download CSV** save local
snapshots through the browser/app download mechanism. Open the downloaded HTML
in your browser to view the offline table and its embedded JSON/CSV downloads.
Snapshots taken before completion explicitly say incomplete. Desktop CSV includes
`collection.state`, `collection.requestedSamples` and `collection.receivedSamples`
metadata rows with the original headset alias in the source column, even when no
sensor sample arrived. CSV text fields, including the alias, are escaped if they
begin with a spreadsheet formula prefix. JSON records the alias and device ID;
HTML names the alias.

Only the latest observation is retained in server memory, including partial
samples after stop or disconnect. **Download before starting another observation,
restarting the server or quitting the app**: those discard the previous report.
Page reloads retain server state. Download requests include an observation ID, so
an old page cannot silently download or stop a replacement observation. Reports
are not uploaded or automatically opened, and may contain device identifiers,
OS builds and sensor paths. Review before sharing. The phone-hosted UI does not
support starting observations.

## What it reads

- Battery percentage, driver charging state, signed battery watts and battery
  temperature, using the same parser as Frame Control's battery details.
  Positive battery watts mean charging on the Frame fuel gauge; negative means
  discharge. `Not charging` alone does not prove a charger is connected.
- CPU utilization from `/proc/stat`; GPU clock from the known Frame devfreq path.
- Named thermal zones in °C, with zone names retained. A thermal zone is not
  automatically a CPU sensor; there is no inferred “CPU temperature” or safe
  temperature threshold.
- hwmon power channels, labels and driver names in watts. `vph` is the measured
  system rail, not power at the wall. CPU `apc*` and GPU `gfx` rails are separate
  readings; do not sum all channels as if they were independent power consumers.
- Fan RPM and the Frame fan driver's raw `pwm1`. No generic percentage conversion
  is assumed. The historical Frame driver reported a percent-like value of 41.
- Named IIO board temperatures, PM8550B input/charge current in amps, and raw
  VCNL4000 proximity if the account can read it. Raw proximity has no inferred
  worn/unworn threshold.

Each metric includes its unit, source path and availability state. Missing,
unreadable or invalid values are JSON `null`, not zero. A missing sensor family
is also listed in each sample's `unavailableGroups`; CSV adds unavailable group
rows. Numeric zero remains a valid reading. The OS build is recorded per sample
when `/etc/os-release` is readable; hostnames, addresses, machine IDs, process
lists, logs, screenshots and application inventories are not collected.

The JSON report contains raw samples and a summary per metric: available and
unavailable counts, numeric minimum/maximum/arithmetic mean/first/last, or the
observed charging states. Means exclude unavailable readings. They are sample
means, not time-weighted energy or battery-runtime estimates. Different sample
availability and intervals must be considered when comparing sessions.

Numeric validity does not establish sensor accuracy. Historical readings
already showed an apparently absent/broken right-display thermistor near
−16 °C. This firmware also reports one charger-lite die sensor at −60 °C.
Those raw numbers remain visible for diagnosis; neither should be used to
infer cooling performance or safety. This tool does not diagnose heat, explain
a spike, predict battery health, or promise power savings.

## Safety and shared-device use

Only file reads under `/proc`, `/sys` and `/etc/os-release` run on the Frame.
The Python sources are sent on SSH stdin and not installed on the headset.
There is no sudo, OpenVR initialization, service call, settings write, process
control, journal query, wake, suspend or reboot. No daemon, telemetry upload or
automatic measurement is added. Redirects above write only to your computer.
The observer itself uses a little CPU and SSH traffic, so label baseline
conditions and avoid interpreting very small changes as savings.

The sampler checks `/tmp/frame-test.lock` on the computer before SSH, and on
the Frame before any probe and before each sample. If a smoke session is active,
it exits 75. A lock appearing mid-run stops the next sample, retains earlier
samples, sets `stopped`, and exits 75. It never removes or acquires another
session's lock. This is an advisory check, not an atomic lease: a smoke session
can start during a file read. Coordinate sessions and defer measurement when
timing overlaps. It does not block someone else from starting a smoke test.

SSH failures/timeouts return a nonzero exit and an explanation, without
presenting a zero or an old report as a successful measurement. Fully missing
sensors can still produce a successful report with explicit unavailable states.
On a connection failure, partial samples buffered on the headset can be lost.

## Evidence and remaining work

Read-only checks on **2026-10-24**, SteamOS **0.5.6**, build
**20261015.6141207**, confirmed battery, CPU ticks, thermal zones, rail power,
fan, GPU clock, board temperatures and charger current through the final
sampler. Proximity was unavailable. Both JSON and CSV paths were exercised;
see [the recorded results](evidence/power-sampler-2026-10-24.json).
No smoke lock was present at the preflight or sampler checks. No settings,
services, application state or device files were changed. This short run is
a parser/transport check, not a controlled baseline or a worn-headset test.

The original planning document is in commit `fe132e3` (2026-09-29). It recorded
an off-head, charging idle baseline of about 4.71 W, CPU zones around 40–45 °C,
and about 8,350 fan RPM on build 20260925.6191901. Those conditions and firmware
differ from the current check; comparisons do not establish a regression.

This change completes only the sampler portion of “Plan: leave it on, but
cheaply.” Controlled worn/home-space, streaming/game load and unplugged
baselines, and the cause of the 2026-09-28 95 °C spike, remain uninvestigated.
Quiet mode, compositor changes, CPU/fan/charging changes and remote-wake tests
are separate work. No controls are offered here. Follow the shared-device
procedure in [testing.md](testing.md#headset-smoke-test) for future experiments.

The accessible HTML export was checked on the same build on **2026-10-24**:
three streamed samples, 91 metric summaries and 276 CSV data rows. Chromium
preview checks at 1280 px and 390 px confirmed the table stays in its scroll
region; both browser downloads matched the original samples. See
[export evidence](evidence/power-export-2026-10-24.json). Ctrl+C retention and
local process cleanup were tested with local subprocess fixtures, not on the
real headset. Screen-reader, Windows and macOS checks were not performed.

Offline validation:

```sh
python3 -m unittest discover -s tests -p 'test_power*.py' -v
bash -n scripts/frame-power-sample.sh
python3 -m py_compile scripts/frame_power_sample.py scripts/frame_power_report.py
```

Fixtures cover units, signed and zero values, missing/malformed/permission-denied
readings, named/discovered channels, unknown charging state, CPU warmup,
summary counts, CSV quoting, strict SSH transport and smoke-lock interruption.

Export fixtures also cover HTML escaping, download round trips, zero versus unknown,
stream completion/failure, smoke-lock stop, timeout, Ctrl+C retention, local child
cleanup, duration bounds and refusing to overwrite reports.

Desktop validation on **2026-10-24** covered API start/stop, a synthetic browser
observation with partial exports, shared-module resource staging under isolated
Python and missing-resource build guards. A real Frame probe under this task's
owned smoke lock correctly returned zero samples with an explicit incomplete
reason; no successful live sensor baseline or native installer run was performed.
See [desktop evidence and limitations](evidence/power-desktop-2026-10-24.json).
