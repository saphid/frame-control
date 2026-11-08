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

## Controlled local parent EOF probe

A separate local Linux probe executed the unmodified `UnixSocket` class and
`PluginWrapper._response_listener` method from Decky 3.3.0 commit
`67196adfa9b299f20dfb0cc932e88a169417b7d5`. Their source-file SHA-256 values
were `cbc62b1f142df0678de0996c00214c0e0fd9cce35cc032daaa40717e49710138`
and `a15487dabf4ac402c13b01c5673dc41ff7bef119103c2f7b21957eb1ab1e2214`,
respectively. An owned Unix socket peer closed immediately after connecting.
The reader returned an empty string at EOF; the parent listener caught the
JSON error and retried without yielding. A scheduled heartbeat never ran,
and the three-second outer deadline killed and reaped only the owned probe.

In the connected-peer control, the heartbeat ran, listener cancellation
propagated and socket cleanup completed. The probe used a private temporary
socket directory and did not modify Decky, contact the Frame, or run an ARM64
VM. It establishes a parent event-loop starvation mechanism under controlled
EOF. It does not establish that EOF occurred in the historical migration
failure, identify which process first failed there, or clear the release hold.

## Repeating the controlled parent EOF probe

[`scripts/framey-probe-decky-parent-eof.py`](../../scripts/framey-probe-decky-parent-eof.py)
makes that source-level experiment repeatable on a desktop with Python 3.10 or
later and Unix sockets. Download these two public files from the exact upstream
commit above; the script refuses any other content before executing it:

```sh
probe_dir=$(mktemp -d)
curl --fail --location --output "$probe_dir/plugin.py" \
  https://raw.githubusercontent.com/SteamDeckHomebrew/decky-loader/67196adfa9b299f20dfb0cc932e88a169417b7d5/backend/decky_loader/plugin/plugin.py
curl --fail --location --output "$probe_dir/localsocket.py" \
  https://raw.githubusercontent.com/SteamDeckHomebrew/decky-loader/67196adfa9b299f20dfb0cc932e88a169417b7d5/backend/decky_loader/localplatform/localsocket.py
python3 scripts/framey-probe-decky-parent-eof.py \
  --parent-source "$probe_dir/plugin.py" \
  --socket-source "$probe_dir/localsocket.py"
```

The script extracts the unmodified `UnixSocket` class and parent response
listener without initializing the rest of Decky. It creates two private Unix
socket fixtures in separate owned Python children. The connected-peer control
must run a heartbeat, propagate listener cancellation and close its socket.
The closed-peer case must publish peer closure and then miss its heartbeat
until the outer deadline. The parent kills and reaps only its own timed-out
child before removing the temporary socket directory. The default budget is
three seconds per concurrent child, configurable between two and ten seconds.

No userspace stack capture is attempted. An initial timer-sampling version
crashed its disposable EOF child while dumping a trace; that failed run was
retained separately and the instrumentation was removed. The probe does not
inspect asyncio task stacks, install signal handlers, attach a debugger or
change security. It uses no headset, SteamVR, plugin settings or live Decky
endpoints.

Exit status zero means the cancellation control passed, the controlled EOF
starvation reproduced and both children were reaped. It does **not** mean
Decky shutdown passed. The report keeps `historicalCauseEstablished` and
`releaseHoldCleared` false. This is an optional investigation tool, not a
replacement for strict native/package gates or locked real-Frame smoke.

## Newer upstream release comparison

Decky v3.3.1 resolves to upstream commit
`ffd103b9c1a4ce5bf305e7c0998eda6e05457dad`. On 2026-11-08, a read-only
AST comparison found these five methods identical to the pinned v3.3.0 source:
`PluginWrapper._response_listener`, `PluginWrapper.stop`,
`PluginWrapper.kill_if_still_running`, `UnixSocket._read_single_line` and
`UnixSocket._listen_for_method_call`.

That comparison does not execute v3.3.1 or rule out other changes in it. It
provides no evidence that upgrading alone repairs this controlled mechanism,
and it does not identify the historical migration timeout's cause. The tested
runtime pin and release hold remain unchanged.
