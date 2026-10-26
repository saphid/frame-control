# Independent Android fixes review — 2026-10-26, round 2

**Verdict: no actionable findings in the frozen Android hardening delta.** The previous Sol findings R1, R2 and R3 are addressed. This is a source-slice review, not a release-readiness verdict.

Reviewer: current T3 Codex runtime, `gpt-6.1-sol`, high reasoning. I performed the review myself, without delegation.

## Exact target and boundaries

- Worktree: `/Users/saphid/.t3/worktrees/steam-frame/feat-phone-screenshot-autosync-108`.
- Branch: `feat/phone-screenshot-autosync-108`.
- HEAD: `ae9df3544239afc1f2cab17ec10fe07f6fe9e657`, plus the frozen uncommitted delta.
- All **15 paths** in `/tmp/frame108-android-fixes-review-20261026-r2.json` matched their SHA-256 values before and after review. Manifest SHA-256: `e3417c56926d08faecb6e5beacaf081c9e4fc395ef494c4de999a4b2282900ad`.
- I inspected the complete tracked delta, the untracked SessionGate and test files, the evidence files, and surrounding engine, exporter, service, activity and connection logic. I checked callers and lock order as well as the changed lines.
- I read the original Opus review, first Opus fixes report, previous Sol review and reproductions, latest Opus fixes report, and `docs/evidence/android-phone-review-fixes-2026-10-26.md`.
- No `CODING_STANDARDS.md` exists in the worktree, its ancestor directories, or the primary checkout root. I read `CONTRIBUTING.md`; no relevant violated rule was found.

I made no repository edits, did not read `.frame_pwd` or unrelated dirty primary-checkout files, and used no device, headset or browser. I made no external writes, commits, pushes, PR changes or releases. Review outputs and local test classes are under `/tmp`.

## Previous Sol findings

- **R1 — addressed.** `SyncEngine.java:668-673` now preserves both the existing journal version and its account-set representation in `copy()`. Setting-only writes on v1 stay valid v1. Reconcile upgrades to v2 alongside its account set at `:285-304` and `:337-343`. The new JVM regression covers constructor preference reconciliation and an explicit toggle before any poll, immediate snapshot/reopen, repeated toggles, and the subsequent migration/baseline behavior. It passed in my independent run. The retained-v1 instrumentation path is present and passed in the parent's supplied API 36 log.
- **R2 — addressed.** `GalleryExporter.java:74-84` acquires the process-wide `EXPORTS` lock interruptibly with a 30-second timeout, and releases it in `finally`. It covers deterministic row lookup, byte copying, publication and cancellation deletion across exporter instances. The order is EXPORTS → settings monitor → engine monitor. Neither Gallery toggle nor startup cleanup acquires EXPORTS while holding the settings monitor; I found no inverse acquisition path. The old exporter must finish its row work before its successor recovers/inserts a row. I independently recompiled the frozen exporter and engine and ran the existing bounded HandoffRace reproduction with an in-memory resolver: the successor waited, the old cancellation deleted only its pending row, and the successor's published row survived with a saved receipt. The native FIFO test separately checks actual published-row existence and original bytes; its passing result is parent-supplied evidence, not my own device run.
- **R3 — addressed.** `ScreenshotDeviceTest.java:487-517` tolerates a missing button while the background library loads and waits up to 15 seconds for a share URI different from the previous one. The test verifies A and B bytes, then checks exactly one final share button targeting B. It no longer treats main-queue idleness as library completion. The cleanup adjustment removes only the fixture URI already proven deleted; other cleanup errors remain visible. I inspected this code and the parent's passing instrumentation result; I did not independently execute instrumentation.

## Fresh pass over the earlier fixes

- **F1:** SessionGate serializes visible status/page/notification effects against session end. Permanent engine close rejects subsequent reconciles and setting writes, and invalidates in-flight journal commits. Late engine assignment and stale-worker finalization are guarded. Gate and takeover tests passed; complete live-service lifecycle behavior remains outside this review.
- **F2:** the generated authorized_keys command terminates an unterminated existing line before appending and remains idempotent. The actual shell fixture cases passed locally.
- **F3:** unchanged listings no longer persist the journal, while retryable downloads/exports continue. Observation resets and account-set changes still commit. The write-blocking regression tests passed.
- **F4:** invalid sizes are excluded per item; unsafe identities, non-finite times and conflicting duplicates still reject a poll. Stability resets and completion after a skipped observation are covered by passing JVM tests.
- **F5:** library snapshots do not create or rewrite storage. Activity parsing/file checks run on its library executor, live-engine selection matches the requested pin, pin changes clear the old list, and results for a no-longer-selected pin are discarded. I found no further actionable sharing regression.
- **F6:** cleanup selects app-owned pending rows in the expected folder, serialized against final publication, and keeps published images. It remains best effort. Provider failure can leave hidden appOnly bytes, particularly on API 29 if Gallery is re-enabled before another cleanup. This documented residual limit is not a newly discovered blocker.
- **F7:** per-account baselines handle absent userdata, established empty accounts, newly appearing accounts, and accounts observed between the SSH and screenshot queries. The migration preserves the intended baseline policy. The shell/parser and account-baseline tests passed.

The workflow trigger and documentation changes are consistent with this scope. I found no new concrete regression requiring a fix.

## Actual verification

All review-generated artifacts are in `/tmp/frame108-android-sol-review-fixes-20261026-r2-evidence/`.

1. **Independent JVM execution:** compiled current SyncEngine, SessionGate, FrameConnection, PhoneIdentity and all three JVM test classes with JDK 17, cached declared dependencies and SDK 36 into a fresh `/tmp` classes directory. Direct JUnit run: **54 tests passed**, exit 0. No Gradle task or repository build output was changed. Commands, compile log/exit and JUnit log/exit are saved there.
2. **Independent local handoff execution:** compiled the current GalleryExporter against those classes and the existing HandoffRace Android substitutes. Compile and execution both exited 0. Output ended with `exists=true pending=false receipt=saved` and `RESULT: published row survived`. This reuses the inspected existing harness and proves the application-level interleaving; it is not MediaProvider instrumentation. See `race.log` and `race.rc`.
3. **Parent evidence inspected:** final clean build log and exit file record success; existing XML totals are 47 engine + 4 gate + 3 connection tests, all zero failures/errors/skips. The frozen API 36 instrumentation log records **six passing tests, no skips**, and supervisor exit 0. I did not rerun assemble, lint or instrumentation. The parent's lint result is 0 errors and 12 existing warnings.
4. **APK hashes independently recomputed:** app `139443c8f3246527ed629731b4f2a099939a2ba7590b628cde415f3f0d7ab996`; test `3a84246a7b40436fd5fc521154541603050805270e21e052e26b31a5fa1e0cc2`. Both match the supplied round-2 evidence.
5. **Freeze/whitespace:** all 15 source/evidence hashes matched again after checks; branch and HEAD matched; `git diff --check` exited 0. Final hashes and whitespace result are saved in the evidence directory.

## Verification limits

Physical locked/Doze behavior, API 29 runtime behavior, complete service Stop/restart during a live headset download, the final phone-to-headset pipeline, iOS APNs/locked Photos behavior, production signing and release are not established here. A stuck old provider write can delay successor exports; the timed lock makes those attempts retryable but does not cancel the stuck I/O. Gallery-toggle I/O on the main thread is an existing disclosed limitation.

The successful read-only headset account listing supports that command only. Historical device evidence from the committed ae9df354 implementation does not establish the frozen fixes. These limits do not create an actionable defect in this reviewed slice or justify a release claim.
