# Guest-root migration shutdown stacks

The historical ARM64 migration timeout still lacks the Python stacks needed
to explain its cause. The signed-package probe now has an optional observer
for the actual migration fixture, alongside its existing strict shutdown gate.

Run the `Syncthing actual Flatpak package` workflow with
`migration_stacks=true` on the desired branch. Its two native matrix entries
enable the observer; the two browser entries retain their normal behavior.
For a prepared local package run, add `--migration-stacks` to the existing
source-bound candidate invocation. `--migration-sampler-wheel PATH` can reuse
the pinned py-spy 0.4.3 wheel offline. Browser mode and non-candidate package
probes refuse this option.

Only root inside the marked private systemd VM can run this observer. It
verifies the native sampler, published Decky loader and observer digests, then
samples UID 1100 processes in the exact migration Decky service cgroup.
PID start ticks, all four UIDs and cgroup membership must agree before and
after every dump. A changed or vanished process loses its captured text.
The observer never signals Decky or changes the normal 90-second stop budget.

The first capture requires an active service and a ready Python HTTP server.
A status-only `HEAD /auth/token` request does not read or retain a token.
Further captures occur at 10, 30 and 60 seconds after the observer first sees
the service deactivating. These times are relative to that observation, not
the exact start of the user's stop command. A clean stop before a window
does not require a capture at that window.
A cgroup that disappears between a stop-state query and sampling is retained
as an explicit diagnostic gap, with no stack text. It cannot replace the
required running baseline.

Each snapshot samples at most eight cgroup processes. Each sampler has a
two-second deadline and drains at most 16,384 stdout bytes and 4,096 stderr
bytes. Reports retain timeout, truncation and unsupported-process errors.
Only a complete, identity-bound Python event-loop stack can satisfy the
required baseline. The observer joins before the root probe reports success,
including when the unprivileged probe fails. The existing dedicated virtio
result channel carries the diagnostic report, avoiding console-line loss.

Focused local tests cover identity changes, bounds, subprocess reaping,
baseline readiness, capture timing, provenance and cleanup. An AMD64 private
systemd VM also captured the actual published Decky Python event loop and
joined the observer. Its service stopped normally in 4.954 seconds with
`Result=success`, `MainPID=0` and `ExecMainStatus=0`. The
[record](framey-migration-guest-stacks-2026-11-12.json) binds the observer,
sampler, loader and fixture sources; the compressed raw record retains the
guest report and both fixture programs. This empty-plugin feasibility test
did not run the Syncthing migration. Hosted actual migration evidence on both
architectures is still required. A current clean
stop or a controlled parent-EOF reproduction cannot establish the historical
ARM64 cause. This diagnostic does not clear that release hold or replace the
locked exact-release Frame smoke.
