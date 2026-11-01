# Battery Tracker integration with current main

Normally merge main `4558a36f58f84840d835f4fc281f12541f15ea94` into prior PR #519 head `bdcffb6f64534dc06d3db3e5eb17349fde1139aa`, producing
tested source `b0f85cf88e21576b80b232dc68b8e140eddd0a54`. Before integration all 18 old checks/five workflows were
terminal: 17 success and AMD64 signed-package failure. Main's nine triggered
checks/two workflows were green. Battery Tracker's exact-archive IPC/pending
SQLite sample fix is still absent from main and remains useful.

Resolve three conflicts while preserving both complete Battery Tracker and
SteamGridDB negative controls, both runner entries and exact-digest installer
dispatches. Whole-checker, installer, receipt/e2e test ASTs preserve current main
outside the intended Battery Tracker changes. All 25 source inputs verify.
Main's TIME_WAIT build/ownership/package/runtime/migration/service sources and
DNS fixture are byte-identical; all 116 status/install policies are preserved.

A first local resolver assertion failed and its shell continued into an invalid
merge containing markers. That unpublished local commit is retained in the raw
record and excluded from this fresh worktree's ancestry. The replacement passes
source audits **before** staging/committing. No history was rewritten.

Local Linux AMD64 validation at the tested source:

- Server: 1965 tests, 15 platform/optional skips. Website:
  18 tests, no skips. Resource warnings remain in the retained logs.
- Published Decky 3.3.0 AMD64: nine cases over Battery Tracker, SteamGridDB,
  RadiYo and Prefix Manager, with every loader/archive pin and 25 source inputs
  checked. Four independent behavior/installation audits pass. Battery Tracker
  verifies private Frame-shaped samples, history/per-app power, pending SQLite
  flush and restart persistence across two repaired parent-only clean stops.
  Independent decoded SQLite snapshots verify contents and integrity; the prior
  backend reproduces forced termination and lost pending samples. This is not
  real battery hardware proof. Expected negatives retain failed compatibility;
  generic clean-runtime flags remain false.
- Isolated Fake Frame: 53 tests, zero skips, 403.281 seconds. All 116
  exact archive pins and outcomes match previous catalog results. Official
  plugin backends are not executed by this transport suite. Independent cleanup
  confirms owned resources absent and pre-existing simulator/images preserved.

The old AMD64 failure is still failed: artifact 13063439836 records watchdog
`Address already in use` during migration. Current main includes #533's bounded
retry for a separately reproduced unowned loopback TIME_WAIT state, but the
owner/socket state of #519's historical collision remains unproven. This source
integration is not a blind rerun, a flake classification or a package pass.
Require every fresh exact-publication-head CI/e2e/native AMD64+ARM64, ownership
and triggered package gate before fresh main/review/required-check/mergeability
gates. No failed/cancelled/skipped required gate is accepted.

Battery Tracker remains partial; SteamGridDB remains broken. Store 130 stays
1.0.1 and separate GitHub 1.0.2 lookup stays unverified. Real Frame recording,
accuracy/history, foreground-app labels, official UI, actual Steam CEF, worn
visuals/controllers and release smoke remain unverified. No Frame, schedule,
PR #113, pre-existing data or security settings were changed. No release.

Raw SHA-256: `4d3244ded33f7315ea3223c2f317ea6b7b538bcc6b6f80a62c93996b9b49adc0`. Full reports/logs/audits/programs are retained.
