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
