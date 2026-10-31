# MangoPeel owned watch lifetime

The exact official MangoPeel 0.0.7 backend leaves its non-daemon inotify thread
blocked in `os.read()` after `_unload` clears the run flag. In an isolated
published Decky 3.3.0 AMD64 run, plugin reload reached Decky's five-second
deadline and required SIGKILL. Discovery alone did not establish a clean
lifecycle.

The managed adaptation is limited to store ID 56, archive SHA-256
`71dc21ce5f9f4ee0573bd927e9b444d45dc47327888ca78ed063c7bcc57bfac1`
and original backend SHA-256
`cb80b8563e4d1a0b58e2b35a16189db9f41a4dc1da563811353a56dd495fa976`.
It replaces only the `Inotify` class. All backend bytes outside that class were
independently compared and preserved. Updated managed installs record
`mangopeel-watch-lifetime`; existing installs need Update/reinstall.

The reader uses a nonblocking, close-on-exec descriptor and bounded readiness
waits. Callbacks run on its owned thread instead of detached debounce timers.
Stop joins that thread before closing the descriptor and clears its watches;
repeat stop is safe. A callback that cannot finish within the join deadline
raises an error rather than closing a descriptor still used by a live reader.

## Verification

- The installed class passed real Linux kernel-event tests for profile writes,
  idle stop, an active callback that must complete before stop returns,
  descriptor closure, no callback after unload, repeat stop and owned removal.
- Published Decky 3.3.0 AMD64 passed selected and multi-profile write RPCs,
  actual inotify updates, a plugin reload with preserved profile bytes,
  replacement-watch activity, and loader shutdown with exit status zero.
  Retained console evidence shows plugin stop in 0.1 seconds without SIGKILL.
  An unrelated profile and the inert fixture process were preserved.
- All eight native probe source fingerprints, the published loader digest,
  official archive digest and installed backend digest were independently
  verified. The full native result and console are in the adjacent JSON.
- The full unit suite ran 1,913 tests successfully with 16 platform/optional
  skips in 250.266 seconds. The three runtime-coverage tests and 16 compatibility
  tests passed; generated compatibility documentation and diff checks passed.

The first native probe correctly exposed the original forced kill, then raced
Decky's queued reload with another RPC. The final probe waits for replacement
discovery. An intermediate process-group teardown sometimes returned status 1
despite a completed shutdown log. The final probe signals only the owned
launcher once and requires exit zero; those earlier results remain recorded,
not treated as passing. Its helpers, containers and temporary runtime images
are owned by the probe and cleaned by its runner.

## Refresh against current main

Main `3978edf7c8ca9d71c87015029983dd1f93ea76f1` is merged into the
MangoPeel branch without rewriting history. Four additive inventory/dispatcher
conflicts retain both MangoPeel and Deck Progress, including Deck Progress's
unchanged-original unload negative control. All other 115 catalog rows and all
116 ID/version/digest/status/installer policies match that main.

On this merged source, native AMD64 MangoPeel again passes actual profile/watch
RPCs, clean reload and parent-only zero-exit loader shutdown. All nine runtime
source hashes were checked; the installed backend was independently reconstructed
from the exact original ZIP plus the one watch-class replacement. Every other
MangoPeel backend byte matches. The affected Deck Progress managed/original cases
also pass their expected controls: 36 literal RPC results, four independently
decoded SQLite snapshots, no managed forced kills and two original forced kills.
The full local reports/consoles were retained and their source hashes verified;
these targeted probes are not a fresh full native-inventory qualification.

The refreshed server suite passes 1,923 tests with 16 platform/optional skips in
243.627 seconds. All three runtime-coverage tests and the generated compatibility
document check pass. Historical hosted results at head `5d17bb6` remain scoped to
that head. Fresh exact-head hosted native AMD64/ARM64, e2e, ownership, every
triggered package mode, current-main and feedback/mergeability gates remain
required. These local tests do not establish overlay, browser, Frame or controller
usability and publish no release.

## Limits

The fixture process supplies a private `MANGOHUD_CONFIGFILE` through real `/proc`
discovery, but it is an inert Python process, not mangoapp or gamescope. This
proves private backend configuration and watch lifetime, not a visible overlay.
The unchanged frontend was not connected to this backend in a browser. Native
ARM64, exact hosted head checks, actual Frame and worn/controller behavior
remain unverified. No real headset was contacted. The direct store metadata
read returned HTTP 403; this evidence makes no fresh live-store version claim.
The compatibility classification remains partial and no release is published.
