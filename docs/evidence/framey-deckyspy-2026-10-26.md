# DeckySpy system monitoring on Frame

Official ID 89, DeckySpy 0.6.7, SHA-256
`2d431a89826ed5cf3fd37258373eb3b46c841c39795aa8b25f83e59f4eee87c7`.
[Redacted results](framey-deckyspy-2026-10-26.json).

The official archive imports `psutil` but does not ship it. Published Decky
3.3.0 reproduced `ModuleNotFoundError: No module named 'psutil'` during backend
startup. The previous catalog's account/external-integration reason was wrong:
this plugin monitors local system metrics; its token is a local reload guard.

Exact managed installs now include unmodified, SHA-256-pinned BSD-3-Clause
psutil 7.2.2 stable-ABI wheels for amd64 and ARM64. The native architecture is
selected remotely and its ELF header checked. Dependencies and their license
stay in this plugin's `py_modules`; no pip, network download, system-library
changes or other plugin imports are involved. [Provenance and license](../../ui/vendor/psutil-7.2.2/README.md).
Existing copies need an explicit managed update or reinstall. Installed receipts
without `deckyspy-psutil-and-battery` stay partial and display that requirement;
they do not inherit the fixed catalog status.

On Frame OS 0.5.6, upstream psutil also misses `max1720x_bat_7-36`: its Linux
battery discovery filters names for `BAT` or `battery`. The plugin-local
fallback preserves native psutil results, then reads supplies whose `type` is
`Battery`. It reads capacity/status and optional time-to-empty in Linux sysfs
seconds, leaves unknown states unknown, and never writes sysfs.

Verification used the **published Decky 3.3.0 executable**, not a hand-built
Plugin instance. Its actual legacy websocket route passed version, CPU,
memory, battery, uptime, process and interface reads on the real ARM64 Frame.
The memory total exactly matched `/proc/meminfo`. No process/network controls
were run. Before starting, the test confirmed template migration sources were
absent so upstream's template migrations could not move existing user data.

Local headless Chromium rendered the exact official frontend in Framey's
opaque iframe, connected through a single trusted SSH RPC pipe to that live
ARM64 backend. CPU/memory/swap/uptime, 100% battery, process rows and interfaces
rendered. A test OOM warning produced a silent visible toast. Native Chromium
keyboard input changed only the private plugin refresh interval from 5 to 6;
backend setting/commit calls and a fresh panel reopening confirmed persistence.
No real media, volume, power, network or process settings changed.

The shared `/tmp/frame-test.lock` protected all device execution. The private
user service had a runtime limit and was stopped/removed, along with its base
and upload. An independent SSH audit confirmed no unit/base/upload or running
service remained. Battery stayed 100 → 100. Normal managed Decky was failed and
the headset panel inactive as found; the lock was released. No headset wipe,
normal service restart or installation outside the removable private user
service occurred. Raw process names, addresses and local guard tokens were
kept out of published evidence.

Local verification also passed all five actual-Decky amd64 regression cases,
the focused fake-Frame pinned install/remove transaction (backend execution
stubbed), 1,648 Python tests (16 skips), and the app tests with Node 24. The
native ARM64 CI gate additionally runs discovery/public calls for this shim.

**Works** covers useful read-only system monitoring, a silent test warning and
private settings while the panel is open. Automatic OOM/low-battery warnings,
resume callbacks, game-time warnings, sound, worn VR and physical controllers
remain unverified. No claim is made for persistent monitoring after closing
Framey's isolated panel.
