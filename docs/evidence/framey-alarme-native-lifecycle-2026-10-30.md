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
