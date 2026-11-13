# Timeout diagnostics integrated with Battery Tracker main

Normally merge exact main `3d6145c640ffe1f9b51923335972ddd513ad0de2` into previous PR #535 publication
`81103c9128164afeb37967b7ae859cf1263477c6`, producing source `eca42ce81ae9e4adb154084f19fbc503405a0f04` without conflicts. Both timeout files
remain byte-identical to that publication. All other main files are byte-identical
outside those two intended files and nine existing evidence files. All 26 native
input fingerprints and all 116 complete catalog rows match main. Battery Tracker,
Steamback and all existing production/test controls remain preserved.

Full local Linux server: **1971 tests**, 15 platform/optional
skips. All three real-child timeout/success/nonzero tests execute and pass,
retaining bounded Unicode diagnostics, timeout propagation, child reaping and
nonzero exit 23. Website: **18 tests, zero skips**. Resource warnings remain in
the raw logs. The normal merge parents, full index tree and each source hash
were independently checked. The published branch remains unchanged at this
local evidence step, preserving its live ARM64 package job.

Previous publication `81103c9128164afeb37967b7ae859cf1263477c6` has independently audited AMD64/ARM64 native,
53-test zero-skip full116 simulator and three AMD64 package scopes. Its ARM64
package is still live/unqualified at preparation. These historical executions
**do not execute this new integration**, whose main has 26 native inputs rather
than the prior publication's 25. No new native, simulator, ownership or package
execution is claimed here. Main's CI is also still pending at preparation.

Require the old jobs terminal, unchanged remote/main guards and no main failure
before a normal push. Every triggered fresh exact-publication CI/e2e/native and
package/ownership gate must pass, followed by exact green current-main CI,
required checks, review/unresolved feedback and mergeability before merging.
The ownership workflow may not trigger for the two guest-only changed files;
no absent execution is claimed. A failure, cancellation or skipped required
gate holds merge/release. Do not cancel a live job to publish this update.

This diagnostic change does not fix or establish the cause of #529's ARM64
hang. Production behavior, timeout budgets, strict nonzero/report validation and
Syncthing's disabled installation policy remain unchanged. Store 130 stays
1.0.1; the separate GitHub 1.0.2 digest remains lookup-unverified. Actual Steam
CEF, official UI, managed Frame and worn visual/controller behavior remain
unverified. No real Frame, schedule, PR #113, pre-existing data or security
settings were touched. No release.

Raw SHA-256: `2b77da9c1d7b106be9923b8bc59c89c52ffed654d296db3aca9e3264c53f6829`. Reports, logs, source bindings and programs retained.
