# Framey unworn exercise with standby gate

At 2026-10-26 01:52 UTC, this PR's `scripts/framey-vr-check.py --exercise`
acquired the shared lock on a real Frame running the `c62bffc8` main bundle.
The new read-only preflight found SteamVR activity 3 (standby), proximity raw
6.3125 and battery 99% before allowing temporary installation or power changes.
The lock owner was unique to this run.

The documented unworn exercise passed: the Frame Control overlay was visible,
stereo compositor pixels changed, `/dev/video99` was captured, a synthetic
trusted OpenVR pointer reached the sample, a live Decky setting was saved and
persisted after a fresh panel reopen, and the quick action, slider and text
field produced their expected values. Native scroll did not move. The test
retagged only its temporary panel window once to recover focus. Public numeric
results are in [framey-vr-standby-gate-2026-10-26.json](framey-vr-standby-gate-2026-10-26.json).
Room-containing stereo and mirror captures remain private in `/tmp`.

Cleanup returned battery 99%, `power.pauseCompositorOnStandby=false` and
`power.turnOffScreensTimeout=5.000000`, matching the preflight. The temporary
power recovery unit was removed, no cleanup errors were reported, and only
this run's lock was released. Local tests also checked that activity 1, 2 or
unknown refuses both `--wake` and `--exercise` before any installation or
power change.

Synthetic pointer events and captures do not prove physical controller use,
wearer-visible readability, optical comfort or VR keyboard behavior. Those
remain unverified.

## Combined v0.4.39 candidate reruns

After #278 and #279 joined main, the combined `bc72c41` branch ran the same
locked exercise three times. The first two runs (02:01 and 02:02 UTC) loaded
the sample UI in Chromium, but SteamVR kept its overlay hidden even after the
existing test-window focus retry. Synthetic input reached no panel control;
both runs failed. The third run (02:05 UTC) showed the overlay without that
retry and passed the sample setting, input, stereo and mirror checks. Every run
restored the original power settings, removed its recovery timer and released
its own lock with no cleanup errors. The [numeric summary](framey-vr-standby-gate-2026-10-26.json)
records all three outcomes.

The intermittent hidden-overlay condition remains a reliability limit. The
runner now records a small read-only diagnostic and refuses to send synthetic
input if the overlay stays hidden after its focus retry. A successful Chromium
panel alone is not treated as VR visibility.
