# Battery Tracker integration with Steamback main

Normally merge current main `2b4d1474ec71573ab91845b46e21f773284bebad` into PR #519 head `f36b5fd9e0ba7242fd6f27846616369fc4b6fc51`,
producing tested source `b562a7dc42d98817a44c55617f0e3419b3439934`. All 18 old-head checks/five workflows passed
and are terminal before publication. Exact current-main signed-package CI is
still pending; this branch update does not qualify a merge or release.

Resolve three additive conflicts while retaining complete Battery Tracker and
Steamback controls, runner entries and exact-digest installer dispatches.
Whole-checker, installer, receipt/e2e AST audits preserve current main outside
the intended Battery Tracker changes. All 26 native source fingerprints and
all 116 catalog status/install policies verify. Main's Steamback private helper,
TIME_WAIT and DNS repairs are retained.

Local Linux AMD64 validation at the tested source:

- Server: 1,968 tests, 15 platform/optional skips. Website: 18 tests, zero skips.
  Logs retain resource warnings.
- Published Decky 3.3.0 AMD64: 11 cases across Battery Tracker, Steamback,
  SteamGridDB, RadiYo and Prefix Manager. Five independent behavior and
  installation audits check exact loader/archive pins and all source inputs.
  Battery Tracker's repaired/original cases use 37/36 RPCs; two repaired clean
  stops flush private pending SQLite samples, preserve history across restart,
  and retain three independently decoded/integrity-checked rows. The original
  backend reproduces forced termination and zero final rows. Steamback's 11/9
  RPC cases independently check private backup, undo and save bytes, clean
  repaired unload/restart and the original forced-stop negative. These are
  private fixture data, not real battery or user-save proof. Generic clean
  runtime flags remain false and expected negative results remain failures.
- Isolated Fake Frame: 53 tests, zero skips, 405.362 seconds. All 116
  exact archive pins and outcomes match prior catalog results. This transport
  suite does not execute every official backend. Cleanup independently confirms
  owned resources absent and pre-existing simulator/image identities preserved.

This packet qualifies only the local source above. A publication adding these
three evidence files requires fresh exact-head CI/e2e/native AMD64+ARM64,
ownership and every triggered signed-package mode, followed by exact green
current-main CI, reviews, unresolved-feedback and mergeability gates. Historical
old-head success does not replace new-head execution. No failed, cancelled or
skipped required gate is accepted.

Battery Tracker remains partial; SteamGridDB remains broken. Store 130 stays
1.0.1; separate GitHub 1.0.2 lookup remains unverified. Actual Steam CEF,
official UI, real Frame recording/accuracy/history, foreground-app labels, worn
visual/controller usability and release smoke remain unverified. No real Frame,
schedule, PR #113, pre-existing data or security settings were changed. No release.

Raw SHA-256: `586b6eaa442b91bf3dba084e69d481059a0c8f2b86068a6d9314dd77931688d8`. Full reports, logs, audits and programs are retained.
