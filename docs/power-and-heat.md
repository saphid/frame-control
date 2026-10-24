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

Offline validation:

```sh
python3 -m unittest discover -s tests -p test_power_sample.py -v
bash -n scripts/frame-power-sample.sh
python3 -m py_compile scripts/frame_power_sample.py
```

Fixtures cover units, signed and zero values, missing/malformed/permission-denied
readings, named/discovered channels, unknown charging state, CPU warmup,
summary counts, CSV quoting, strict SSH transport and smoke-lock interruption.
