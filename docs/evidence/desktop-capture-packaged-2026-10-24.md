# Packaged Desktop Capture, 2026-10-24

Base: `de931bc`. Package: Linux x86_64 **v0.4.17**. Device: real Frame,
SteamOS **0.5.6**, BUILD_ID **20261015.6141207**. Host: lxso2.
[Sanitized state and response evidence](desktop-capture-packaged-2026-10-24.json).

## Result and issue boundary

The packaged app discovered the nested KDE compositor and both automated
Desktop **Capture** button clicks succeeded. The repeat returned HTTP 200,
`Content-Type: image/png`, `X-Capture-Source: panel`, and Content-Length
1,209,980. The app decoded a fresh, nonblank 1920×1080 image and displayed
the Desktop panel badge. No further product failure was reproduced or fixed.

This does **not** establish the full visible-desktop condition in
[#73](https://github.com/saphid/frame-control/issues/73). `xwininfo` reported
the desktop window `IsViewable`, and gamescope confirmed focus after
`vrcmd --showdashboard valve.steam.desktopgame.0`. However, SteamVR still
reported that overlay `not_visible`. There was no worn-headset visual check.
The observation proves capture of a mapped nested compositor, not its visible
presentation to a wearer. Do not close #73 from this evidence.

The issue screenshot shows a desktop panel in the headset view while Desktop
Capture logs “no app panel is open in the headset.” The reporter used SteamOS
0.4.5, gave no Frame Control version or reproduction steps, and has not replied
to the maintainer's 0.4.3 update request. The duplicate page function was already
fixed; [PR #152](https://github.com/saphid/frame-control/pull/152) subsequently
improved unknown-state diagnostics. Its [earlier investigation](panel-discovery-2026-10-24.md)
was blocked from starting a desktop by another task's lock. This run adds a
current-package capture observation, without reproducing the older failure.

## Procedure

1. Read-only preflight found Game Mode active, full Plasma inactive, Steam and
   SteamVR running, battery 99%, no nested desktop/runtime and no test lock.
2. Compared the retained AppImage's SHA-256 with the live v0.4.17 release asset
   digest: `b1b8eb82bf73a227b2cd36e8f0ef3a2ebdf7967c5853efb08a9634f38227015d`.
   Extracted an independent copy; `cmp` confirmed its `frame_touch.py` matches
   the base checkout. No payload was edited.
3. Started the package's own AppRun, bundled server and Python on Xvfb `:139`
   with private config/cache/data/profile, telemetry and update checks disabled,
   and `--no-sandbox --disable-gpu`. Used the existing authorized `ssh frame`
   identity. T3 preview opened the package server page but does not attach to
   the existing Electron window. The literal Electron button test used the
   same Playwright-over-loopback-CDP workflow as the earlier packaged tests.
4. Acquired `/tmp/frame-test.lock` with atomic `mkdir` and wrote an owner marker.
   Rechecked no nested runtime or Plasma was present. Started SteamOS's
   `/usr/bin/steamos-nested-desktop` in the owned transient user unit
   `fc-issue73-desktop-20261024.service`, using Steam's display/session variables.
   `RuntimeMaxSec=180s`, `TimeoutStopSec=15s` and `KillMode=control-group` bounded
   the session. This launches a desktop panel inside Game Mode; no full Desktop
   Mode switch was sent.
5. In the actual packaged Electron window, navigated Tools → Capture & Live →
   Desktop and clicked Capture with `locator.click()`. The first click event
   recorded `isTrusted=true`. The page selected the KDE compositor on `:0`;
   the production screenshot path used window `62914560`. Requested the desktop
   dashboard, read back focus/visibility, and clicked Capture again. Recorded
   response metadata, fresh decoded image dimensions and canvas pixel range.
   No direct screenshot API call was substituted for these button clicks.
6. Ran the packaged `frame_touch.py panels` read-only over SSH to retain its
   exact discovery result: one focused KDE compositor panel, app ID 0, 1920×1080,
   display `:0`, with no diagnostic `why` field.

## Cleanup and limits

The owned desktop session ran **09:43:48–09:45:33 UTC** (105 seconds). Hid the
dashboard to restore its initial hidden state, stopped only the owned unit,
and verified it was unloaded/inactive with MainPID 0. No Plasma/KWin desktop
process or nested runtime remained; gamescope's focusable/focused lists were
empty again. Released only this task's lock, after checking its owner marker.

Delayed readback at **09:46:39 UTC** confirmed the lock absent, Game Mode active,
full Plasma inactive and the original Steam, vrserver and vrcompositor PIDs
still running. The Game Mode service invocation was unchanged. Battery was
99% at cleanup and 100%/Full on the delayed check. Closed both owned preview
tabs, Electron and Xvfb; their processes and X socket were gone. No test server
remained. No reboot, installation, security/global setting change or full
Desktop Mode transition was performed.

The nested desktop journal included gamescope WSI/Vulkan-hook warnings. No
warning was dismissed. Capture produced nonblank compositor pixels, but this
run does not assess their usability to a wearer. Private image files stayed
outside the repository; only state and response metadata are published.

The initial CDP `response.body()` read yielded zero bytes despite successful
decoding in the page. The repeat verified the PNG Content-Length, fresh image
dimensions/source/selection and a 2,011,278-byte PNG exported from the canvas.
The initial raw-body measurement is a harness limitation, not evidence of a
product capture failure. No Live video, Control input, physical monitor, FUSE
mounting or hardware rendering was tested. Older SteamOS and other packages
remain outside this observation.

## Offline verification

`python3 -m unittest discover -s tests -p test_touch.py -v`: **42 tests passed**,
including the production page's Node panel behavior tests, duplicate-function
guard, absent versus empty panel diagnostics, alternate displays, capture/input
target validation and discovery deadlines. JSON parsing and `git diff --check`
were also checked. No new regression test was added because this is an
evidence-only change with no reproduced product defect.
