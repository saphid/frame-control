# v0.4.38 real Frame release smoke

On 2026-10-26 at 01:47 UTC, the exact `v0.4.38` tag
`d87b863aa3c61c9833045b29ba79c7534a351ef4` passed `scripts/frame-smoke.sh`
on a real Frame running SteamOS 0.5.6 build `20261022.6153909`. The wrapper
atomically acquired `/tmp/frame-test.lock` with a unique owner, then read
SteamVR activity 3 (standby), proximity raw 6.3125 and battery 100%. It ran
the smoke only after that preflight.

All 13 smoke steps passed. The ARM64 test title ran. The x86_64 title correctly
reported its runtime missing. The Windows executable ran through the ARM64
Proton path. The final cleanup found no test processes and removed the reserved
smoke titles. The read-only postflight still found activity 3 and battery 100%;
the wrapper released only its own lock. The public numeric summary is
[v0438-release-smoke-2026-10-26.json](v0438-release-smoke-2026-10-26.json).
Private raw logs and process paths remain in `/tmp` and were not published.

The new built-in shared-lock preflight on this PR's branch separately passed
the same 13/13 smoke steps at 01:46 UTC, with activity 3, proximity raw 6.3125
and battery 100% before the run. The lock was released after cleanup. The local
`tests.test_smoke_cleanup` suite passed 20 tests, including refusal on a busy
lock and release after a failed preflight. The built-in preflight was **not**
part of the v0.4.38 tag; that release used the external lock wrapper described
above.

These checks did not involve a worn headset or prove Framey panel visibility,
physical controller interaction, or optical comfort.
