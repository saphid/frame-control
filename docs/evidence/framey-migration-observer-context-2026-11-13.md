# Migration observation error context

The opt-in actual-migration run [43335061722](https://github.com/saphid/frame-control/actions/runs/43335061722)
at `3fe1c0d383aa836a6b708e9e993fcd337de89789` failed its diagnostic on
both architectures. Both observers first reported D-Bus `NoReply`, then an
unavailable query helper; neither captured a running baseline. The migration
services themselves stopped cleanly: AMD64 in 1.736 seconds and ARM64 in 10.464
seconds. This is an observer failure, not a reproduced migration shutdown hang.
The capped eight-error arrays do not reveal the total number of errors.

The observer now records its start time and retains context beside each of the
first eight observation errors: monotonic iteration start, elapsed observation
time, query/sampling phase, fixed migration-cgroup presence before and after,
and whether baseline sampling had begun. An unreadable cgroup is recorded as
unknown, not absent. A separate counter includes errors beyond the retained
limit. These directory observations provide diagnostic context only; they do
not authorize a sample or claim the cgroup remained present between reads.
The existing error strings, sampling identities and stop/query budgets remain
unchanged. No bus retry or service-control operation was added.

All 95 focused and neighboring tests passed without skips. Injected failures
verify timestamp retention, cgroup disappearance, unreadable cgroups, no fake
baseline, capped detail and total counting. The [source-bound record](framey-migration-observer-context-2026-11-13.json)
includes the original failed artifact digests and the [test log](framey-migration-observer-context-2026-11-13.log).
The changed observer has not yet run in an actual native migration VM. These
local tests do not establish the historical ARM64 shutdown cause or clear the
locked exact-release real Frame smoke. No Frame or worn-headset check ran.
