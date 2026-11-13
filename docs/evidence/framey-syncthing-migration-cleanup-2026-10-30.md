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
instance or edits registry state. This observer does not change production
services. Persistent entries and query failures still fail. The report retains the last listing
and successful cleanup elapsed time; a timeout includes the listing in its
error. Existing private data/config/certificate and unit/receipt checks remain
in place before cleanup can be credited.

## Verification

A deterministic regression executes the migration fixture's actual final
cleanup statements with a transient application listing. Original main fails
at the immediate assertion; the repaired code observes drain. The registry
regressions cover persistent entry refusal, failed-query refusal and preserving
another application's
similarly named entry. Python syntax and diff checks pass.

A local signed-package/Decky/migration VM run at `7071b3c` passed an independent
audit of all 13 input sources, signed content, two-way sync, 17 service
lifecycle assertions, 18 ownership refusals, migration preservation and owned
cleanup. Native AMD64/ARM64 Decky CI and AMD64 package/browser HTTP artifacts
at that same head also passed their independent audits. Exact-head ARM64
package and production-parent browser CI remain required before merging.
These results do not establish managed Syncthing installation or real Frame/controller usability. No headset,
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
even on stop failure. Regressions cover a clean stop beyond the command
budget, a forced manager timeout and a persistent stop job.

## Packaged loader shutdown signaling

A full local replay of `232c6aa` still failed. Its
[independent audit](framey-decky-stop-exit-failure-2026-10-30.json) matched all
124 exact-source fingerprints and the checksummed result packet. Migration
registry cleanup passed in 0.331 seconds, but the owned Decky stop completed
with `ActiveState=failed` and `Result=exit-code` in 2.034 seconds. The retained
loader tail contains `asyncio.exceptions.CancelledError` during plugin
shutdown. This is a failed package gate; the packet contains partial results.

The prior generated production unit and fixture used systemd's default
`KillMode=control-group`, which signals the packaged launcher and its children.
The pinned [official Decky 3.3.0 release unit](https://github.com/SteamDeckHomebrew/decky-loader/blob/67196adfa9b299f20dfb0cc932e88a169417b7d5/dist/plugin_loader-release.service)
uses `KillMode=process`. The generated Frame Control unit now uses
`KillMode=mixed`: send the initial SIGTERM to the packaged launcher, which
forwards it, while retaining systemd's final cgroup-wide cleanup. No timeout
or accepted exit status is relaxed. This applies on install/update; no live
headset unit was changed. Duplicate signaling is a hypothesis, not a proven
cause of the captured failure.

Every existing isolated Syncthing service VM now starts the actual released
Decky through an owned user unit with the same mixed policy, including both
native ownership CI architectures. The stop requires inactive state,
`Result=success`, zero exit status and MainPID, and the original PID gone.
Exit-code failures, forced timeouts and persistent jobs remain failures.
Reports retain KillMode, ExecMainCode and ExecMainStatus. The generated-unit
transaction regression checks the policy through install/update/rollback.
All 98 Syncthing tests and three Decky transaction/release tests pass.

The new [local AMD64 native-service audit](framey-decky-mixed-service-local-2026-10-30.json)
passed all ten source fingerprints, 17 lifecycle assertions and 18 ownership
refusals. Actual released Decky stopped with mixed policy in 7.559 seconds,
inactive state, success result, zero exit status and MainPID. This is not a
controlled reproduction proving the prior cancellation's cause. The full
signed-package/production-parent replay subsequently failed as recorded below.
Updated exact-head CI and independent artifact audits remain required before merge. Compatibility and physical-controller claims remain unpromoted.


## Dashboard queue starvation after restart

The full local replay at `e061dfefeb52bafbb8c5ff66d7202a8c3143b175`
[failed its restarted dashboard gate](framey-syncthing-dashboard-queue-failure-2026-10-30.json).
The independent audit matched all 124 committed inputs, the complete
7,538-byte checksummed packet and the checksummed gateway diagnostic chunks.
Migration cleanup passed in 0.295 seconds. The final unit stop was
inactive/success with zero exit status/MainPID in 2.866 seconds, although
Decky's log still contains a plugin-shutdown cancellation. Neither the mixed
policy nor a successful unit status proves an error-free plugin shutdown.

The [failure capture](framey-syncthing-dashboard-queue-failure-2026-10-30.png)
shows Running and the configured folder, but Devices displays
`Error: Decky backend timed out`. All native RPC replies and production SSH
calls succeeded. Six serialized successful dashboard reads span 31.72 seconds;
queue waiting consumed the same 30-second deadline as active RPC execution.
A clock-controlled regression reproduces starvation with six individually
successful 5.5-second reads. It fails on the previous code and passes after
the repair.

Keep one fetch active, the 16-item waiting cap, 30-second queue expiry,
cancellation behavior and fixed managed-backend path. After dispatch, each
request now receives the existing full 30-second RPC execution budget.
Queue waiting and execution are bounded separately, so the combined bound
is up to 60 seconds rather than 30. Expired waiting work is never dispatched;
hung active RPCs still time out. No backend, systemd or fixture stage timeout
was increased. This fixes actual frontend starvation rather than removing
the dashboard's error-free readiness requirement.

The updated browser regression, all 98 Syncthing, 30 panel and three Decky
tests pass.
A fresh full package/production-parent replay and exact-head CI are required;
the failed `e061dfe` run is not credited as package or restart proof.


## Successful full queue-budget replay at `c013e99`

The full isolated AMD64 replay at
`c013e9900a570aa686952761f3d32b5f465afa44` passed. Its
[independent audit](framey-syncthing-queue-budget-local-2026-10-30.json)
matched all 124 committed input fingerprints and the complete 1,007,583-byte
checksummed packet (SHA-256
`259647c4278ed0414edf842f5690f104cbe5a3688be00712e2679174af301371`).
Signed bundle verification, actual two-way sync, 17 service lifecycle
assertions, 18 ownership refusals, 12 migration results, 20 signed-process
identity checks and preserving uninstall passed. The exact migration registry
drained in 0.264 seconds. Owned Decky stopped with inactive/success state,
zero exit status/MainPID and mixed policy in 2.552 seconds. The retained
console has no shutdown-error or cancellation marker; this observation does
not prove the cause of the earlier shutdown failures.

Both the private bridge and unchanged production HTTP parent completed
Running/Stopped/Running/Stopped with error-free dashboard DOM observations,
setup discovery without the manual port fallback and distinct actual signed
process identities after restart. Production transport handled 65 HTTP calls
and 74 native CEF requests; all completed, with bounded timing/observer
records and restored owned resources. All eight captures were reviewed via
four distinct images and SHA-256 equality for the repeat states. The retained
production-parent [Running](framey-syncthing-queue-budget-running1-2026-10-30.png)
and [Stopped](framey-syncthing-queue-budget-stopped2-2026-10-30.png) captures
show the corresponding panel states; the private-bridge Running capture
also shows the configured folder and peer. Repeated pixels alone are not
restart proof: the audit separately binds the distinct signed process IDs
and native service observations to those stages.

Browser renderers retained seccomp/no-new-privileges sandboxing. The VM,
actual user service, listeners, synthetic receipt and owned fixture resources
were cleaned; no host bus, network device, real Frame, active person session
or pre-existing user data was used. CEF and the managed receipt remain
synthetic. This is local AMD64 package/HTTP/browser proof, not ARM64 browser,
real Steam CEF, managed installation or physical-controller proof. Exact-head
signed-package CI remains a separate merge gate.

The prepared auditor initially expected an input flag absent from the exact
producer schema. Its schema check was corrected against the committed
producer; the actual report explicitly records `statusImportProfiling=false`,
which remains required. No runtime success condition or evidence checksum
was relaxed.


## Migration-loader cancellation found in current-head CI

At exact head `c013e99`, AMD64 signed-package artifact `13002674726`
(SHA-256 `d91f06cee239eb30c2f63fece9ee54bd6013feef12c6882ccf6267f587a09831`)
and browser/HTTP artifact `13003872603`
(SHA-256 `7f3a119747b085fbd3b64f4e45e049007bdc1471832d9a0fff2e75be1df7c2a0`)
passed package, signature, exact-source, sync, ownership and migration/data
preservation audits. The private browser's Running and Stopped captures were
inspected; repeat states match by checksum, with distinct signed processes
separately proving restart. These are successful CI jobs, not failed or
cancelled GitHub jobs.

However, both retained consoles contain `Error during shutdown:` and
`asyncio.exceptions.CancelledError` from the separate migration fixture's
Decky loader. The later mixed-policy managed Decky service stopped with
inactive/success state, zero exit status/MainPID in 1.362 and 1.539 seconds.
That does not erase the earlier migration-loader errors. The
[exact-source audit](framey-syncthing-migration-decky-cancellation-ci-2026-10-30.json)
retains this distinction. The migration fixture still launched Decky directly
and sent SIGTERM to its entire process group; no manager-result or clean-log
gate covered this separate loader. Duplicate signaling remains a hypothesis,
not a proven cause.

The follow-up runs migration Decky in its own uniquely named owned user
unit, using the same mixed signal policy and shared strict stop observer.
Both migration and ordinary service fixtures now inspect the retained loader
log and refuse the captured shutdown-error/cancellation markers, even if the
manager reports success. Normal `Cancelling tasks...` cleanup messages are
allowed. The migration result retains its actual manager stop and confirms
removal of its owned fixture unit. Legacy service/data/receipt assertions and
all existing timeout budgets remain required.

All 100 Syncthing regressions and three Decky transaction/release tests pass,
including a refusal case derived from this retained CI traceback. Compilation
and diff checks pass. A fresh full local package/production-parent replay and
exact-head native/package CI are still required. No headset, production
session, compatibility policy, release or tag was changed.
