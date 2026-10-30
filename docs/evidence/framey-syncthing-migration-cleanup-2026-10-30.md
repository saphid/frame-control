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

A local signed-package/Decky/migration VM run at `7071b3c` passed an independent
audit of all 13 input sources, signed content, two-way sync, 17 service
lifecycle assertions, 18 ownership refusals, migration preservation and owned
cleanup. Native AMD64/ARM64 Decky CI and AMD64 package/browser HTTP artifacts
at that same head also passed their independent audits. Exact-head ARM64
package and production-parent browser CI remain required before merging.
This is a test-harness repair, not evidence of managed
Syncthing installation or real Frame/controller usability. No headset,
pre-existing user data, security settings, tags, or release were changed.

## Owned Decky stop observation

The production-parent package artifact from run `41099306702`, job
`124213203773`, failed a separate cleanup step. The
[failure audit](framey-decky-stop-timeout-2026-10-30.json) matched all exact-head
and VM source hashes and the complete checksummed result packet. Migration
registry cleanup passed in 0.181 seconds, but the later blocking command to
stop the owned Decky service exceeded its general 35-second command budget.
The service uses the manager's default 90-second stop budget. The failed
fixture lost the job result and loader log tail, so it establishes neither a
clean delayed shutdown nor a hung or forced shutdown. It remains a failed gate.

The fixture now requests the owned service stop without blocking systemctl,
observes the actual manager state for a bounded 100 seconds, and requires an
inactive unit, `Result=success`, zero MainPID and the original PID gone.
A forced manager timeout or persistent stop still fails. The stop state,
manager timeout and elapsed time are retained, and loader logs are printed
even on stop failure. No timeout, kill policy or production service is changed.
Three regressions cover a clean stop beyond the command budget, a forced
manager timeout and a persistent stop job; all 41 focused Flatpak tests pass.
This follow-up requires a new exact-head full package/browser replay and CI.
