# Syncthing runtime failure evidence — 2026-10-31

The raw-peer runtime probe previously printed only the last 5,000 characters of
each log on failure. Its successful result omitted the loader console, and the
ownership workflow did not upload a separate runtime console. The retained
shutdown failure on PR #503 therefore cannot establish the helper's process
state at failure or the precise shutdown cause.

The host runner now saves captured stdout and stderr in
`syncthing-runtime.console.log` on success, failure, or timeout. The workflow
uploads it even when a probe fails. A successful result binds that file by
SHA-256 and retains the loader console and its separate hash. On an exception
inside the native probe, diagnostics include the exact owned helper's PID,
state and parent PID, whether its socket directory remains, and the full logs
available at that point. No environment variables or command lines are dumped.

Three tests execute actual subprocesses: exit 23 retains more than 12,000 output
bytes without becoming success; a timeout retains emitted stdout/stderr and
still raises; success replaces a stale console file.

The native AMD64 positive control uses published Decky 3.3.0, the unchanged main
candidate helper and pinned Syncthing v2.1.7 peers. Two-way sync, restart, private
RPC reads, wrong-key 403 and normal helper/process shutdown pass. All five
runtime input fingerprints and the loader/helper/console hashes were checked.

A separate owned source copy deliberately pauses only the plugin before
requesting loader shutdown. The loader reports shutdown without its forced-kill
fallback; the probe then fails its unchanged helper-shutdown assertion. The
14,980-byte retained console includes the full available logs and a sleeping
helper with its plugin parent and socket directory still present. No successful
result JSON is written. This validates the diagnostic failure path; it does not
reproduce or explain the historical CI failure. The injected source is not part
of the product or CI probe.

The timeout path retains only output emitted before timeout. The existing
forced peer-cleanup path still prints the tail of that peer's log and was not
exercised here. ARM64 and final-head hosted CI remain required. Syncthing stays
blocked and unselected; its helper, production code and all catalog entries
match base main `8ebe9acda1cb1174120f07fb42b39afcc1ed8c9c`. No real Frame,
Steam CEF, worn view, physical controller or release is verified by this work.

[Results, source fingerprints, negative injection and limits](framey-syncthing-runtime-failure-evidence-2026-10-31.json).
