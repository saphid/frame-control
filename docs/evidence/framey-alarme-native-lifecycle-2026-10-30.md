# AlarMe paused timer restart, 30 October 2026

AlarMe 1.6.3, store 124, has published archive SHA-256
`17d4166a9e98979df5fdb07c7eae42317acd54a453d3b82757508f971193c0fe`.
Its unchanged startup resumes paused timers if their original deadline is
still future, and deletes them if that deadline elapsed. A paused timer can
therefore tick or disappear after restarting Decky, although its saved state
still says paused. The [original failing check](framey-alarme-original-paused-restart-failure-2026-10-30.json)
retains the first native reproduction and its exact source/archive hashes.

The managed installer adds one paused-state guard at startup, restricted to
this store ID, folder, archive digest and original backend digest. All other
backend bytes, manifest/API1 convention, JavaScript and license remain
unchanged. A different archive digest receives no adaptation. Existing
managed copies require update or reinstall; installing this change does not
rewrite an existing copy automatically. Compatibility remains partial.

The [native AMD64 result and source fingerprints](framey-alarme-native-lifecycle-2026-10-30.json)
come from the published, digest-pinned Decky 3.3.0 executable discovering the
managed plugin and dispatching its actual API1 RPCs and events. The disposable
container has no external network, host home, session bus or devices. Private
timer settings use zero volume, subtle mode, no auto-suspend and no sleep
inhibition. The check verifies pause/resume/cancel, idempotent cancel, exactly
one silent completion event, preset deduplication and persistence, and
stopwatch laps/pause/reset and persistence across a complete loader restart.
Both a long paused timer and one whose original deadline elapsed remain
frozen after restart. The elapsed paused timer can then resume for its frozen
duration and completes once. The unchanged backend, restored from the same
published archive, independently reproduces both failures in a negative case.

Every loader stop sends SIGTERM only to the loader, allowing it to own plugin
shutdown, and requires exit 0, two complete shutdown log entries and no
shutdown error, cancellation exception or pending-task warning. All four
stops across the positive and negative cases exited 0 in 0.214 seconds each.
Earlier development attempts signaled the entire process group and raced
plugin cleanup; those harness results are retained in the JSON and are not
claimed as product shutdown failures. Owned processes and container/image
were removed, and private timer/preset/stopwatch state was cleared.

Validation: the focused store transaction suite passed 59 tests, including
exact-digest installation and refusal to apply this shim to a changed archive.
All three runtime coverage checks, 16 compatibility checks and 50 app tests
passed. The full server suite passed 1,895 tests in 222.753 seconds with
16 platform skips and no failures. Compilation, generated-document and diff
checks passed. Exact-head CI/e2e and native ARM64 remain required before
merging. Native CI is configured to run this positive case and the
unchanged-backend negative case on both AMD64 and ARM64.

This run does not retest the earlier browser controls or real ARM64 Frame
backend. The repair on ARM64, browser interaction after restart, audio,
alarms/reminders, sleep inhibition, Steam overlays, closed-panel notification
behavior, wearer-visible pixels and physical controllers remain unverified.
No headset was contacted, no schedule changed, and no release was published.

## Completed native CI and browser follow-up

The [independent exact-head CI audits](framey-alarme-native-ci-2026-10-30.json) at `3ec43ad6a5af1df55a8190015f7802cc18190511` passed on AMD64 and ARM64, including the repaired and unchanged-original paused-restart cases. Each job verified 35 probes and 31 published archive digests; both logged test-merge checkouts have the same complete tree as that exact head. The reports do not embed separate source fingerprints: identity is bound by the actual checkout tree. Both positive/negative cases report two zero-exit complete loader shutdowns each, but raw loader consoles are not retained in the CI artifacts. The ARM64 repair is verified within this private native scope.

The [separate AMD64 browser restart replay](framey-alarme-browser-restart-2026-10-30.md) verifies both paused cards across a clean loader restart and actual frontend Resume/Cancel controls through the private synthetic bridge. Its three images were inspected. Production HTTP, actual Steam CEF, sound, sleep inhibition, real Frame pixels and physical controllers remain unverified. Its auxiliary fixture is separately fingerprinted outside the tested product commit.

The branch subsequently absorbs main `d89291e` through a normal merge, preserving the original Terminal import-failure regression alongside both AlarMe cases. The earlier run limits above apply to their original evidence only; completed follow-ups do not establish that the refreshed final head passed CI. Fresh applicable checks, e2e, native AMD64/ARM64 and package jobs, plus entirely green current main, remain required before merge. No headset or schedule was changed.

The [refreshed local AMD64 native replay](framey-alarme-main-refresh-2026-10-30.json) at merge commit `c2908e6d2756b2cb124967cde6591706da193d2b` passes both AlarMe cases and separately reproduces the unchanged Terminal import failure without any backend RPC or PTY input. All seven recorded source hashes per replay match that merge commit; the AlarMe cases report four zero-exit complete loader stops. The subsequent evidence/catalog update changes no runtime source in those recorded inputs. Fresh final-head CI remains required.

Historical source `cd12ae455b20e03bab9825d47ab46fb829964740` subsequently passed all 18 checks and all five workflows. The [completed source audit](framey-alarme-completed-source-ci-2026-10-30.json) retains both native jobs (36 probes/31 pinned archives each), the exact e2e tree and all four signed-package audits, including artifact/checkout/source/signature/full-packet/runtime/sync/migration/preservation and strict shutdown identities. All distinct package captures were inspected. Native/package raw loader consoles are absent, so complete-log checks remain source-bound guest/probe evidence.

After all original workflows finished, the branch normally absorbed main `445df0a6d1247dde2f40c156c4586381be9cd91d` without conflicts. Both compatibility evidence updates, AlarMe's paused-timer fix and main's host shutdown verifier are retained. The old green source does not qualify the refreshed head; fresh exact-head CI/e2e/native/package gates and current main must pass before merge. Compatibility remains partial. Audio, actual sleep inhibition, production browser/backend integration, real Steam CEF/Frame, worn visibility and physical controllers remain unverified.


## Refresh onto main d3ae60e with retained available consoles

Main `d3ae60ebed19829e3a3ae43ed1ea3766e0cee45f` was merged normally at
`8dc574de`. Five test-inventory conflicts preserve the existing AlarMe branch
and all 31 main probe conditions (36 branch bodies), including Ludusavi,
Deck Progress, Wine and Shotty. All 116 catalog policies and the other 115
complete catalog records are preserved. Main's input/keyboard, IPC and console
capture sources remain unchanged. Main's ARM64 package gate is still incomplete.

Tested source `7764694ceed5b4e89a47855d55f65ee4736d2e2f` also fingerprints
AlarMe's unchanged lifecycle helper and shared RPC client in native reports.
The product repair and complete AlarMe probe/helper bodies are unchanged.
All 93 focused store, compatibility, runtime-coverage, native-console and Wine
unload-evidence tests pass. A fresh isolated AMD64 published Decky 3.3.0 replay
independently verifies all 17 report source hashes and the pinned loader/archive,
reconstructs the exact original/managed backend bytes, and passes 39 repaired
and 38 original-control RPCs. Paused long/elapsed deadlines, explicit resume,
one silent completion, preset and stopwatch restart behavior pass. The original
still incorrectly ticks after restart and deletes an elapsed paused timer.

Four source-bound parent-only loader stops return zero. Complete available
post-cleanup consoles and hashes are now retained. Generic cleanup records
already-exited loaders without claiming another signal. Each console retains
two JSON diagnostics; their phase/cause, error-free consoles and global clean
plugin shutdown remain unverified. Private-file preservation and parent-only-stop
assertions are source-bound; complete independent filesystem/process snapshots
were not retained. No new owned runtime containers or image tags remain.

[Current refresh audit](framey-alarme-maind3ae60e-refresh-2026-10-31.json)
and [raw report, source audit and full unit output](framey-alarme-maind3ae60e-refresh-2026-10-31-raw.json.gz)
retain this result. Fresh final-head hosted checks/e2e, full native AMD64/ARM64
matrix (42 probes / 34 archive pins / 17 source fingerprints per architecture),
ownership and all triggered package modes remain required. Earlier hosted/browser
results remain scoped to their recorded revisions; no new browser replay is
claimed. Sound, actual sleep inhibition, production HTTP integration, live Steam
or CEF, managed Frame and wearer/controller behavior remain unverified.
Compatibility stays partial; no headset or hourly schedule was accessed and no
release is published.

## Current main 0082d79 refresh

Normal merge `eb9f167e13b03ac7411715b884e1c1aa57d36d12` resolves three inventory conflicts between the existing AlarMe repair and main `0082d79a3ff9a9338e49dd5c83bbe25aa9e784b4`. Independent source comparison preserves all 32 main probe conditions/37 branch bodies, all 34 main cases, the complete AlarMe probe/production repair, all 116 classification/install policies, the other 115 complete catalog rows and AlarMe's complete prior row. Main's keyboard/input, IPC and native console sources are byte-preserved. The full matrix now expects 43 probes, 35 archive pins and 17 source fingerprints per architecture.

All 93 focused tests pass. A fresh isolated AMD64 published Decky 3.3.0 replay passes 39 repaired and 38 original-source API1 RPCs, with original paused/elapsed deadline failures retained. Independent audit reconstructs the pinned original/managed backend, checks all 17 source fingerprints and each complete available console hash. Four parent-only zero-exit stops and private-file checks remain source-bound. No new owned containers/image tags remain. Available console JSON diagnostics remain unattributed; error-free consoles and global clean plugin shutdown are unverified.

[Current refresh audit](framey-alarme-main0082d79-refresh-2026-10-31.json) · [complete native report, source audit and unit/native logs](framey-alarme-main0082d79-refresh-2026-10-31-raw.json.gz).

The final evidence commit changes documentation only after that tested merge source. Previous head `982f2982` has five successful terminal workflows; those do not qualify this new SHA. Fresh final-head hosted checks/e2e, native AMD64/ARM64, ownership, PC and all triggered package modes remain required, together with exact current-main, feedback, rules, mergeability and integration review. No new browser, sound, actual sleep inhibition, production HTTP, live Steam/CEF, managed Frame, wearer/controller or release proof is claimed. No headset or hourly schedule was accessed.
