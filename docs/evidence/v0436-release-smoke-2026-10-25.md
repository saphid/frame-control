# v0.4.36 release smoke on a real Frame

On 25 October 2026 at 22:59 UTC, the release branch ran
`scripts/frame-smoke.sh` from a physical Linux host against a real Steam Frame.
The script and its Python implementation were byte-identical to the
`v0.4.36` tag `1701e622dc1f9888560412a058fe816b19ca7e79`.
The headset reported Frame OS 0.5.6, build `20261022.6153909`.

The test acquired `/tmp/frame-test.lock` with a unique owner marker before
reading device status or changing test titles. Its first read showed SteamVR
activity level 3 (standby), proximity raw 6.3125, and battery 99%. The test
ran only while that lock was owned. It released only its own marker and lock
after the final cleanup.

All **13 of 13** smoke steps passed: cleanup of reserved leftovers, devkit
service read, status read, install/launch/remove for reserved ARM64, x86_64
and Windows test titles, and final cleanup. The test did not pair a key. The
test output was saved locally under `/tmp/frame-v0436-smoke-results/`; this
summary omits the headset identifier and private device status fields.

The headset was in standby. This test does not show wearer-visible game or
Framey pixels, controller input, live Decky settings, or plugin actions.
See [release v0.4.36](https://github.com/saphid/frame-control/releases/tag/v0.4.36)
for the tagged installer and checksum checks.
