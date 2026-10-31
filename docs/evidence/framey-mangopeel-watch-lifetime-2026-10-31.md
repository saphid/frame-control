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
It replaces the `Inotify` class and adds a scoped child-IPC EOF prelude and
adapter. All other published backend bytes were independently compared and
preserved. Updated managed installs record `mangopeel-watch-lifetime` and
`mangopeel-ipc-eof`; existing watch-only installs need Update/reinstall.

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

## Previous refresh

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

## Refresh against main dd12031

Main `dd12031f55ccbcba01aa07296080495df1935af1` was merged normally at
`560989d6ed2b801e9e0ea2d427f0eeeddf473ce6`. Five additive conflicts preserve
both MangoPeel and Ludusavi cases, store tests and runtime coverage. Main's
keyboard, IPC and Ludusavi source bytes are unchanged. The store installer
matches main plus only the MangoPeel watch adaptation; all 116 version, digest,
classification and install policies and the other 115 catalog rows are preserved.

On this merged source, the 61 store tests, 16 compatibility tests and three
runtime-coverage tests pass. The generated documentation check also passes.
Targeted native AMD64 Decky 3.3.0 probes pass for MangoPeel, Deck Progress
managed/original controls and Ludusavi. Ten source fingerprints per report
and all 34 published-archive inventory digests were independently checked.

MangoPeel again passes real kernel-watch updates, private profile writes,
reload and parent-only loader shutdown with exit zero. Its managed backend
was independently reconstructed from the pinned original and watch-class
replacement. Deck Progress retains 36 literal RPC results, four independently
decoded SQLite snapshots, zero managed forced kills and two expected original
forced kills. Ludusavi retains three literal RPC results, bounded discovery,
the original missing-dependency negative and four parent-only zero-exit stops.
Their complete case-specific consoles were independently checked. The owned
runtime image and containers are gone.

This refresh did not rerun the full host unit suite or full native inventory.
Earlier hosted and full-suite results remain historical. Fresh final-head CI,
e2e, native AMD64/ARM64, ownership and all triggered package modes remain
required. These private backend probes establish no actual overlay, integrated
browser, real headset or controller behavior. No release was published.

## ARM64 failure and scoped IPC follow-up

The fresh hosted ARM64 run at `555f9642e687b9049cd2f314c711e616b9cbba0c`
failed its final-shutdown assertion: reload stopped MangoPeel in 0.1 seconds,
but final unload reached Decky's five-second deadline and required SIGKILL.
The [failed job](https://github.com/saphid/frame-control/actions/runs/41176405202/job/124464760801)
is retained as a failure. The passing local AMD64 run did not qualify ARM64.

The follow-up adds the existing child-process EOF adapter used for the exact
managed Deck Progress archive. Decky 3.3.0's original IPC loop can spin on an
empty closed-peer read without yielding. The adapter ends that connection's
loop and preserves subsequent connections and normal dispatch. Its source is
unchanged. Only the exact MangoPeel archive receives the adapter and import
prelude; other archives and the parent loader are untouched. The watch-class
replacement is unchanged. A new receipt marker makes watch-only copies request
an update while retaining the partial compatibility classification.

At frozen source `f64a7190ceeb666f453ff77af941ae87a5395575`,
local checks pass: 62 store tests, 17 compatibility tests, four IPC behavior
tests and three runtime-coverage tests. They include changed-archive refusal,
published-byte preservation, old-receipt update guidance, EOF starvation,
partial frames and subsequent connections. Native AMD64 again passes actual
kernel-watch updates, private profile writes, reload and parent-only final
shutdown with loader exit zero, two 0.1-second plugin stops and no forced kill.
Ten source hashes, the unchanged adapter hash, the installed backend reconstructed
from the prior watch-only source plus the fixed prelude, and the complete
case-specific console were independently checked. Owned runtime resources were
cleaned.

This is a candidate repair for the observed ARM64 failure. Fresh final-head
hosted ARM64, AMD64, complete CI/e2e/ownership and all package modes remain
required. It does not yet prove the ARM64 root cause resolved. Earlier passing
heads remain historical; no failed gate is waived and no release is published.

## Limits

The fixture process supplies a private `MANGOHUD_CONFIGFILE` through real `/proc`
discovery, but it is an inert Python process, not mangoapp or gamescope. This
proves private backend configuration and watch lifetime, not a visible overlay.
The unchanged frontend was not connected to this backend in a browser. Native
ARM64, exact hosted head checks, actual Frame and worn/controller behavior
remain unverified. No real headset was contacted. The direct store metadata
read returned HTTP 403; this evidence makes no fresh live-store version claim.
The compatibility classification remains partial and no release is published.
