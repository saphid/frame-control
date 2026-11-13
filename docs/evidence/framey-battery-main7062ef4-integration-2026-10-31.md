# Battery Tracker integration with current main

## Announcement

Battery Tracker 0.2.0/store 67 retains its scoped child-IPC EOF repair after normally integrating main. Published Decky 3.3.0 AMD64 verifies two clean parent-only stops, pending battery-sample flush and SQLite persistence across restart. The previous managed backend still reproduces forced termination and lost pending samples. Compatibility remains **partial**; no real battery, plugin UI, managed Frame or wearer/controller proof.

## Source and verification

Tested source `db9824f4071b224e4a6bdccb6800b330e74288b2` normally merges main `7062ef4d81d7fa25e1562d22d0b1b92fa526b499` into prior PR [#519](https://github.com/saphid/frame-control/pull/519) head `0c921258d1cd5367d2683d1d1eaafeaac90cd652`. The publication commit adds only this three-file evidence packet. The runtime-input conflict was resolved retaining both Battery Tracker and TabMaster helpers. Whole-checker/installer AST comparisons preserve main outside the prior Battery Tracker changes, including TabMaster and Simple Timer controls, all other native cases/e2e assertions, 115 other complete catalog rows and all 116 rating/install policies. Mandatory full-catalog CI/cache/e2e files match main exactly.

- Full server: 1960 tests, 15 platform/optional skips. Website: 18 tests, zero skips. Both pass.
- Published, digest-verified Decky 3.3.0 AMD64: eight native cases across Battery Tracker, TabMaster and Simple Timer bind all 21 source fingerprints. Battery repaired/prior controls complete [37, 35] RPCs. Positive parent-only stops finish in [0.196, 0.215] seconds with no forced kill, no recorded owned descendants and an unrelated sibling preserved. Pending samples flush to SQLite and persist across a loader restart. Both captured databases are independently base64-decoded, SHA-256 checked, opened read-only, integrity-checked and compared row-for-row with reported state.
- Previous managed control takes 5.195 seconds, forces a plugin kill and loses pending samples; it remains an expected failure. Independent exact-archive installation/removal verifies the EOF prefix/helper, prior managed backend, original archive members, removal of the unnecessary root flag and managed receipt. No real battery/user database is used.
- TabMaster 47/48/47 RPCs preserve private settings/backup/restart and original/prior-managed negatives. Simple Timer 31/10/18 RPCs preserve four positive clean stops, settings/deadline persistence and both negative controls. Original unload hooks complete on positive stops. Generic runtime-console clean qualification remains false.
- Isolated Fake Frame: 53 tests in 397.758 seconds, zero skips. All 116 exact archive pins verify; 69 install/remove results and 47 refusals, including every reason, equal the previous complete integration. This transport/installer suite does not execute official backends.
- Independent owned cleanup verifies all owned containers, volumes, networks, images and temporary configuration gone. The pre-existing simulator identity/start/restart count and shared image tags remain unchanged.

## Limits

This is local combined-source AMD64 proof. Historical hosted results belong to older heads; new published-head full CI/e2e/native AMD64+ARM64/ownership and every triggered package mode remain required. Existing socket/JSON diagnostics remain where recorded. No globally clean runtime, real battery hardware, Battery Tracker browser/graph, actual Steam CEF, managed Frame, wearer/controller or release proof. No headset, schedules or pre-existing data touched. Fresh exact-main/head/feedback/mergeability gates remain mandatory before merge, and release stays held for every release-commit/tagged installer/checksum/publisher/locked Frame gate.

[Summary](framey-battery-main7062ef4-integration-2026-10-31.json), [raw reports, database snapshots, logs and verifiers](framey-battery-main7062ef4-integration-2026-10-31-raw.json.gz), SHA-256 `a3a09a760ff3e10f52395b05e075bb8bc29634261d84986bf234d1d74c224f75`.
