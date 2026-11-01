# Retain captured output when a package probe times out

Tested source: `97bf8a26a4c639d85e5bbb29407c68b644a5c47a`, based on main `4558a36f58f84840d835f4fc281f12541f15ea94`.

[PR529 ARM64 package job 124720832525](https://github.com/saphid/frame-control/actions/runs/41263313415/job/124720832525) failed at
`b451f49a5cc2e9cfbb45398abfd7f0eda313e073`. GitHub artifact 13066869143, ZIP SHA-256
`438b8b0c13d19f97477e266581f6388ccfe81d701db5cf8e10e96200027d6a95`, retains the failed guest report and journal.
The owned migration Decky service reached its 90-second stop deadline and
systemd SIGKILL; the migration subprocess later hit its 360-second timeout.
Its underlying shutdown hang remains unproven. Earlier install and two-way
sync results do not qualify migration, final service checks or uninstall.

The package guest captured migration/service stdout and stderr, but printed
them only after `subprocess.run` returned. `TimeoutExpired` bypassed those
prints. Both nested probes now use the existing bounded timeout diagnostic
path, extracted into `run_captured`. It records argv, elapsed time, deadline
and the final 10,000 characters of each available stream in
`PROGRESS['timedOutCommand']`, then raises the original timeout. Successful
results, nonzero return codes, strict report assertions, VM guards, production
code, blocked installer policy and every timeout remain unchanged.

A controlled child replaces only argv and the timeout in each actual
migration/service call expression. Both original call sites lose the progress
diagnostics; both repaired sites retain stdout/stderr and still raise.
All four owned children are reaped. An AST audit restores the entire old module
by reversing only the capture refactor; success checks and deadlines match.

All 100 package-related tests pass with no skips, including three focused
real-child tests for bounded Unicode output, timeout/reaping, unchanged success
streams/return value and nonzero failure. The focused three also pass alone.
They compile the real guest functions without importing guest-only GI.
The final timeout fixture uses valid UTF-8 replacement-character bytes so
Windows text-mode pipe readers need not decode intentionally malformed bytes.
The full local server suite was running separately when this packet was written;
it is not a completed verification claim here.

This closes a diagnostic gap; it does **not** repair or qualify the underlying
ARM64 shutdown hang. Captured output can still be absent when a child emits
nothing. No ARM64 package VM replay or real Frame test was run locally. Fresh
exact-head CI/e2e/native/ownership/all triggered package modes and current-main
review/merge gates remain mandatory. Release and headset usability remain
unverified. No headset, schedule, security setting or pre-existing data changed.

The hash-bound raw packet retains the control harness/results, exact two source
files, focused/package logs, authenticated failed-artifact inventory and full
failed report/console/input/head bindings. The larger payload manifests/build
logs remain in the original authenticated artifact, not this small packet.
