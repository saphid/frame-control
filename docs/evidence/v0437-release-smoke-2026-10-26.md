# v0.4.37 release smoke on a real Frame

On 26 October 2026 at 00:27 UTC, a physical Linux host ran the release
`scripts/frame-smoke.sh` against a real Steam Frame. The smoke scripts were
byte-identical to tag `v0.4.37` (`5239dae1a82c35635ef89f59eac9721c5014e2ed`).
The headset reported Frame OS 0.5.6, build `20261022.6153909`.

The test acquired `/tmp/frame-test.lock` with a unique owner marker before
reading the headset. SteamVR activity stayed at 3 (standby); initial proximity
raw was 6.3125 and battery was 99%. The test released only its own lock after
cleanup. Battery read 100% afterward.

All **13 of 13** smoke steps passed. ARM64 and Windows test titles installed,
launched, and were removed. The x86_64 title installed and was removed; its
launch reported that Steam Linux Runtime 4.0 was found but not installed, so
this result does **not** establish x86_64 game execution. Devkit properties and
status reads passed. No key was paired. The final cleanup removed the reserved
test titles and processes. The private result remains under
`/tmp/frame-v0437-smoke-results/`; this summary omits headset identifiers and
device status details.

Because the headset was in standby, this test did not verify wearer-visible
pixels, physical controller input, a Framey panel, or official Decky plugin
settings in VR. Those checks remain on the [worn checklist](../framey-vr-check.md).
