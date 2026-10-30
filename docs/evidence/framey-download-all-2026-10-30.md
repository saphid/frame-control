# Download All 1.1.0 managed queue bridge

On 2026-10-30, a fresh official Decky store read confirmed ID **131**, version
**1.1.0**, SHA-256
`0641231eec139e3231e7b5369d0dbacefd686b52e3f2fffb39384876881408da`.
The checked fixture matches those published archive bytes. Its original
frontend cannot subscribe to downloads in Framey. Its backend only logs UI
messages; backend discovery alone cannot prove download functionality.

## Managed scope

Only that exact ID, archive, manifest and frontend receive the
`download-all-local-queue` receipt shim. The original backend and GPLv3 license
remain unchanged. The managed frontend SHA-256 is
`62f1fbb5636335bde268f0461d70dc03ee7ea2d2630f0e6957dba248523cd2e9`.
Existing installed copies require Update/reinstall; an older receipt retains
the broken classification.

The opaque plugin iframe gets a narrow subscription and queue-batch facade.
The parent binds requests to the current iframe, panel session and installed
archive receipt. Fixed Frame Control code runs in trusted Steam CEF; plugin
code and arbitrary property paths never cross that boundary. Only local
client `0` download rows and bounded scalar fields are returned. Both legacy
and current callback shapes have local fixture coverage.

A batch validates every selected app before making changes, rejects stale or
repeated revisions and already queued/completed apps, sorts smallest first,
appends after the current queue and resumes its head. Each native operation
is awaited; refusal, timeout or panel closure stops subsequent operations.
A partial failure reports how many queue calls completed and never emits a
success toast. Native void returns prove submission only, so the success
message says **Submitted**, without claiming downloads completed. Earlier
successful operations are not rolled back after a later failure. A native
operation already in flight cannot be canceled; a late reply never continues
a timed-out batch. A replacement panel cannot submit another batch until that
native call settles; a permanently pending native call keeps mutations blocked.
Subscriptions unregister on close, API replacement or idle
expiry. No wake, game launch or controller input is involved.

## Evidence

- [Browser report](framey-download-all-browser-2026-10-30.json) and
  [capture](framey-download-all-browser-2026-10-30.png): Google Chrome
  **156.0.8078.79**, actual managed official component and production Framey
  host in an opaque `allow-scripts` iframe. CSP blocks plugin network.
  Synthetic native Steam objects drive Scheduled, All and size-limit filters,
  smallest-first append, preservation/resume of the existing queue head and a
  deliberately refused SetQueueIndex. Exact native call sequence passed; no
  later app or Resume call followed that failure. The screenshot shows the
  stopped-queue message and synthetic queue counts. This is desktop fixture evidence.
- [Native report](framey-download-all-native-2026-10-30.json): actual published
  Decky **3.3.0 x86_64** discovered the managed plugin and passed its logging
  RPC in a network-, device- and user-session-isolated container. It does not
  test Steam queue changes. CI runs the same case on native AMD64 and ARM64.
- Contract tests execute the production CEF bridge, iframe facade and headset
  parent routing. They cover private-field stripping, remote-client exclusion,
  invalid/stale/duplicate selection, an app completing during a batch,
  concurrent batches, partial failure,
  timeout/late completion, replacement-panel refusal while a native call is still
  pending, panel identity, stale replies and subscription cleanup.
- Managed install tests preserve backend/license bytes and check the exact
  frontend transform, receipt, archive pin and removal. The fake-Frame test
  checks actual HTTP/SSH installation, managed frontend hashes and removal;
  it stubs plugin backend execution. All three final focused fake-Frame tests
  passed in 72.895 seconds; the unique project, containers and volumes were
  removed afterward. All 56 store tests and four download-bridge tests passed;
  the final browser replay also passed after the mid-batch completion check.
  The full local unit suite completed 1,773 tests with 16 skips and no failures;
  those skipped checks are not verified by this run. A follow-up regression
  reproduced two overlapping native calls after a timeout and panel replacement.
  The fix retains the native promise gate until settlement; all four focused
  bridge tests and the opaque Chromium replay passed afterward. The test also
  verifies that a fresh panel can submit again once the old native call settles.

Repeat the isolated browser test with:

```sh
python3 scripts/framey-test-download-all-browser.py --browser /path/to/chrome --output /tmp/download-all-evidence
python3 scripts/framey-test-decky-runtime.py --case 131 --output /tmp/download-all-native.json
```

## Limits

No real Frame was contacted for this change. Actual Steam callback values and
queue mutations, real downloads, ARM64 Frame backend execution, headset panel
rendering, wearer-visible content and physical controller operation remain
**unverified**. The plugin is **partial**, not works. The optional full
116-plugin fake catalog audit was not run in this pass (no archive cache was
mounted); the checked-in pinned archive transport tests run separately.
Exact-head CI/e2e/native checks must pass before merge. No release is authorized
by these fixture results: release still requires all installer, checksum,
publisher and locked real-Frame smoke gates.
