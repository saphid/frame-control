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
