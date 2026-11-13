# Junk-Store About and read-only installed metadata

Junk-Store 1.1.13 (official ID 84) now renders its About and Dependencies tabs
without the `local_per_client_data.installed` crash recorded in the
[script-entrypoint audit](framey-script-entrypoints-2026-10-26.md). It remains
**partial**. The catalog and both store views use the same updated reason.

The library snapshot omitted the entire `local_per_client_data` object. The
official frontend dereferences it to display its dependency controls. Under the
shared headset lock, a read-only probe confirmed that the real Frame exposes
this object for the two Proton runtimes, but neither has an `installed` boolean.
Across 1,106 app overviews, 41 had `installed: true`, none had `false`, and 1,065
had no installed boolean. Those absent values must not be relabelled as false.

The snapshot adds one bounded scalar per app: a Steam-supplied boolean or null.
Framey's detached overview creates a minimal metadata object, copying `installed`
only for a boolean. Null leaves that property undefined. No client IDs, paths,
other metadata, live Steam objects or methods cross the iframe boundary. Eight
scalar rows remain accepted, and running-app updates preserve library metadata.
The snapshot still refreshes at panel open; it is not a live installation feed.

## Actual ARM64 backend and local Chromium

The unmodified, hash-verified official archive ran in published Decky 3.3.0 ARM64
on Frame OS 0.5.6 using a private, bounded, removable user service. Legendary was
absent; no dependency installer, runtime install, login, game operation or custom
backend download was invoked. The exact plugin and loader digests are in the
[redacted results](framey-installed-context-2026-10-26.json).

Local Chromium ran the actual Framey host and official frontend in an opaque
iframe. The production receipt-bound bridges read the real Steam library and
called the official ARM64 backend's static menu actions. About content and its
tab list, Dependencies controls, Back, close/reopen, and About again passed.
No dependency buttons were pressed. The real library counts matched the probe.

The optional localhost websocket was blocked by the test relay CSP; RSS was
deliberately denied. Outer status/install/check replies were fixtures; incomplete
outer extension/status and running-context replies are excluded from the plugin
claim. The screenshot still used the catalog reason from before this follow-up.
Dependency installation, login, game operations, RSS, websocket operations,
shortcut changes, deployed headset HTTP and worn VR remain unverified.

## Cleanup and regression checks

The initial cleanup SSH timed out while the private Decky unit was deactivating.
Recovery checked the matching lock owner, killed only that exact test unit, and
removed its private base, unit file and archive. A fresh locked audit independently
confirmed unloaded/inactive/PID 0 and no artifacts, then released its lock. Normal
managed Decky/panel services stayed inactive; battery was 99 → 99. No power-setting
action ran. Local relay and owned browser tab are closed.

- Full Python suite: 1,628 tests, 16 skipped, no failures; focused panel: 22 passed.
- Framey action/running Node contracts passed, including true/false/unknown,
  malformed metadata, detached values, old rows and running-update preservation.
- Both site test files passed. Generated docs and diff checks passed.
- All 116 exact official archives passed the fake-Frame audit: 60 installed/removed,
  56 expected blocks; disposable project removed. Backend execution is stubbed in
  that harness. The fresh official store has 116 entries, no audit errors, and an
  unchanged ID/version/digest set.

No new works claim is made. Catalog totals remain **4 works / 49 partial / 52 broken
/ 11 N/A**; only Junk-Store's verified scope and remaining limits change.
