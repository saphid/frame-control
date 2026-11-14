# Battery Tracker integration with main's DeckyParty repair

## Announcement

Battery Tracker 0.2.0/store 67 retains its exact-archive child-IPC EOF repair after normally integrating merged DeckyParty repair #518. Published Decky 3.3.0 AMD64 verifies clean parent-only stops, buffered SQLite sample flush and persistence across restart; the prior managed backend still force-kills and loses pending samples. Compatibility remains **partial**. Real battery hardware, graphs/plugin UI, actual Steam CEF, Frame and wearer/controller behavior remain unverified. Nothing is released.

## Combined source and verification

Prior published PR #519 head `0ed5b06ed5b2942492f4a6ad96448e3d977ebf49` normally integrates main `de5eb65ff954381cec0df7b1f339f6916abee3d2` at tested source `ed54d5ad6d861e5ac22100d2ea8ab0436ca74678`. Input/negative-control conflicts retain both Battery Tracker and DeckyParty helpers and independent cleanup. Whole-checker/installer AST comparisons preserve main outside Battery Tracker's prior change: other 36 runtime bodies, 33 native cases, installer/e2e assertions, 115 complete catalog rows and all 116 ratings/install policies. Mandatory catalog CI/cache/e2e files match main. All 22 native inputs bind the tested source.

- Full server: 1961 tests, 15 platform/optional skips. Website: 18 tests, zero skips. Both pass.
- Published digest-verified Decky 3.3.0 AMD64: ten native cases. Battery repaired/prior controls complete [38, 35] RPCs; polling counts reflect this actual run. Repaired parent-only stops [0.225, 0.214] seconds; previous forced-kill negative 5.195 seconds. Two captured SQLite snapshots independently decode, hash, pass read-only integrity checks and match exact expected rows. Pending samples flush and survive restart; prior forced termination loses them. Independent exact-archive install/remove reconstructs backend/EOF adapter/receipt, removes the unnecessary root flag and preserves other original members and the existing actual-user battery-source adaptation. Only private test data is used.
- TabMaster 47/48/47 and Simple Timer 31/10/18 retain private settings/backup/restart, original unload hooks on positives and original/prior-managed negatives. DeckyParty repaired/prior 15/8 retains authenticated private operations, three repaired reloads in [0.366, 0.365, 0.364] seconds and its prior forced-kill reload at 5.275 seconds. A later clean replacement stop does not qualify that failed reload. Owned identities reap and unrelated siblings survive. Generic runtime-console clean qualification remains false.
- Isolated Fake Frame: 53 tests in 400.054 seconds, zero skips, all 116 exact pins. All 69 install/remove results and 47 refusals/reasons match the prior complete Battery Tracker run. This transport suite does not execute official backends.
- Independent cleanup verifies owned containers/volumes/networks/images/config absent. Pre-existing simulator identity/start/restart count and shared image tags remain unchanged.

## Older-head artifacts and remaining gates

The separate completed-package packet binds older head `0ed5b06ed5b2942492f4a6ad96448e3d977ebf49`, which passed 18 checks/five workflows and recorded published native AMD64/ARM64, full catalog, ownership and all four package modes. Its source hashes and reports remain older-head proof. The combined source needs new exact-head full CI/e2e/native AMD64+ARM64/ownership and every triggered package mode. Exact current-main CI and fresh head/main/checks/all runs/required checks/feedback/mergeability/integration gates remain mandatory before merge. Socket/JSON diagnostics and expected negatives remain retained. No globally clean runtime, new browser/graph, real Frame or release proof. No headset, schedules or pre-existing user data touched. Release remains held for all exact release-commit/tagged-installer/checksum/publisher/locked-Frame gates.

[Summary](framey-battery-tracker-mainde5eb65-integration-2026-10-31.json), [raw reports/database snapshots/logs/verifiers](framey-battery-tracker-mainde5eb65-integration-2026-10-31-raw.json.gz), SHA-256 `365c69ed0a630654e1c449fbc95fc61e4830ed94f01a1e052c162dcab623aa39`.
