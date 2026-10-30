# Syncthing migration post-stop instance cleanup, 2026-10-30

Main `043085b16cdc5529312c5cb8ad91ebb3bd588080` failed the AMD64 signed-package
job in run [41096005290](https://github.com/saphid/frame-control/actions/runs/41096005290/job/124201812165).
The independent [failure audit](framey-syncthing-migration-cleanup-failure-2026-10-30.json)
matched all 26 declared exact-head sources and 13 VM input sources. Signed
content installation, two-way sync and the initial package/service cleanup
passed. The later migration fixture failed its immediate final `flatpak ps`
assertion after stopping/removing its private legacy service. This remains a
failed run and cannot satisfy a release gate.

That assertion did not retain the last registry rows or descendant process
identities. The evidence does not establish whether it observed registry lag
or a process still finishing teardown. The repair waits up to the existing
60-second service-probe budget for the exact application entry to disappear,
with a 10-second bound on each read-only `flatpak ps` query. It never kills an
instance, edits registry state, or changes a production service. Persistent
entries and query failures still fail. The report retains the last listing
and successful cleanup elapsed time; a timeout includes the listing in its
error. Existing private data/config/certificate and unit/receipt checks remain
in place before cleanup can be credited.

## Verification

A deterministic regression executes the migration fixture's actual final
cleanup statements with a transient application listing. Original main fails
at the immediate assertion; the repaired code observes drain. All 38
Flatpak tests pass (including seven cleanup and 23 signed-package contract tests), including persistent
entry refusal, failed-query refusal and preserving another application's
similarly named entry. Python syntax and diff checks pass.

A local signed-package/Decky/migration VM run is being checked separately.
Exact-head AMD64/ARM64 signed-package and browser CI remain required before
merging this repair. This is a test-harness repair, not evidence of managed
Syncthing installation or real Frame/controller usability. No headset,
pre-existing user data, security settings, tags, or release were changed.
