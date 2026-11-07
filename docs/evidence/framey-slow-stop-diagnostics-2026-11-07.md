# Observing a slow stop before the fixture is killed

The [historical ARM64 migration timeout](framey-migration-stop-timeout-2026-11-06.md)
did not retain a loader stack. A later clean stop cannot identify that failure's
cause. The cause and release hold remain unresolved.

The package VM now takes a read-only process and loader-log baseline before
stopping either owned Decky fixture. If systemd still reports `deactivating`,
it takes up to three further snapshots after 10, 30 and 60 seconds. Each slow
snapshot is flushed to the captured console before systemd's existing
90-second budget can kill the fixture. The final stop record also contains
the baseline and any slow snapshots, including when the stop assertion fails.

Snapshots contain only the fixture's exact cgroup members, PID start ticks,
parent PID, state, CPU ticks, and up to eight threads' wait channels and readable
kernel stack bytes. They inspect at most 32 processes. Membership and start
ticks are checked again after inspection; changed identity is reported as
unreliable. Loader-log tails are capped at 8 KiB each and do not change the
reader position. Missing processes, denied kernel-stack reads, and other
diagnostic errors are recorded. The observer does not read environment or
command-line arguments, attach a debugger, send signals, or change security.

The existing strict stop result, exit status, process reaping and loader-log
assertions remain required. Diagnostics do not extend the manager or outer
wait budgets and do not turn a timed-out stop into a pass. Actual signed-package
and migration checks still run in the networkless, disposable VM; no Frame is
involved.

Local tests exercise the actual observer against private proc/cgroup fixtures,
bounded log tails, foreign-group refusal, missing processes and stack files.
Controlled manager-state tests prove that three slow snapshots precede a
forced-stop failure and that denied diagnostic reads cannot mask that failure.
Fresh hosted AMD64/ARM64 package runs are still required. Kernel stacks are
not Python coroutine stacks; a recurrence may require further investigation.

No reproduction of the historical hang or root-cause fix is claimed here.

## Hosted evidence on the original PR head

Exact head `b877196de24c3b9cd892550f978cea55eb8d11db` passed all 19
checks. Nine uploaded artifacts were independently checked against their ZIP
digests, producer jobs, exact checkouts and source fingerprints. These include
both native Decky architectures, both ownership jobs, fake-Frame e2e and all
four signed-package modes. This qualifies that recorded head's evidence;
integration with later main still requires fresh qualification before merge.

The package artifacts contain eight clean owned Decky stops: service and
migration for AMD64 standard (`13567293520`), AMD64 browser HTTP
(`13567294657`), AMD64 production-parent HTTP (`13568126446`) and ARM64
(`13567358475`). All eight retained a baseline with six owned cgroup processes,
CPU/start ticks, thread wait channels and loader-log tails. Stops took between
1.118 and 10.478 seconds, including baseline collection. None retained a slow
snapshot or reproduced the historical timeout. Every stop passed the existing
strict result, exit-status, reaping and loader-log checks.

All 94 observed thread kernel-stack reads returned `PermissionError`. Those
limits are retained explicitly; wait channels, CPU baselines and loader tails
were readable. No security setting was changed to obtain a stack. These are
kernel observations, not Python coroutine stacks or proof of the old cause.

Hosted Ubuntu server job `128349772981` executed all five new observer and
slow-stop regression tests without skips. Its synthetic checkout
`19a7465e08c73a8cea5f51546b1e0722b12cab3d` has the same tree as the recorded
PR head (`b258c251c4cae5d9a7931695c08051b9f90d292d`). The three slow snapshots
preceding a forced failure were verified in controlled tests; a real slow
stop was not observed in these package runs. No real Frame was contacted.
