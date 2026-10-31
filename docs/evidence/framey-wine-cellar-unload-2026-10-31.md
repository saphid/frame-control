# Wine Cellar child unload, 2026-10-31

Wine Cellar remains **partial**. This repair covers the exact managed official
0.2.1 archive, SHA-256
`7e077b933c234414d172b5c6d1c804b026bf39fa4e18e6663495a282637031e8`.
Update or reinstall an existing managed copy to receive the
`wine-cellar-ipc-eof` receipt marker.

Published Decky 3.3.0's
[`UnixSocket._listen_for_method_call`](https://github.com/SteamDeckHomebrew/decky-loader/blob/v3.3.0/backend/decky_loader/localplatform/localsocket.py)
dispatches empty IPC EOF repeatedly without yielding. On parent shutdown, the
Wine Cask helper exits but the plugin's async shutdown cannot finish reaping it;
Decky then force-kills the plugin after five seconds. Replacing asyncio's
subprocess API alone did not fix the native failure. This repair applies the
existing child-local IPC EOF fix to the exact managed Wine Cellar backend and
bounds helper/supervisor waits inside Decky's stop budget.

The [raw native report](framey-wine-cellar-unload-2026-10-31.json) retains the
complete console for the repaired and prior-source controls, process identity
samples, two read-only `GetState` replies and twelve source fingerprints.
The [independent audit](framey-wine-cellar-unload-2026-10-31-audit.json) checks
source, archive, fixture and console hashes against the tested files.

On native Linux AMD64, the digest-pinned published Decky 3.3.0 loader discovered
the managed plugin. Two parent-only SIGTERM stops both returned zero in 0.201
seconds, with each exact helper gone/reaped and no forced plugin kills. The
first unload left a client socket open for `_unload` to close; the second closed
it first, after restarting Decky. No process-group shutdown was used to qualify
either stop. Restoring the exact previous managed Python source reproduced a
zombie helper and one forced plugin kill after 5.227 seconds; that negative
control is explicitly not clean qualification.

Three host tests use real children to check exact-child reap with an untouched
sibling, a TERM-ignoring child killed/reaped inside the deadline, and supervisor
restart followed by unload. Before the final receipt marker and native-probe
edits, the full host suite passed 1,927 tests with 16 skips. Final affected
installer, lifecycle, IPC, runtime coverage, socket and compatibility tests passed
88/88. The fake-Frame pinned-official-plugin install/remove test passed in 74.364
seconds in a uniquely named Compose project; its containers, volumes and network
were removed. These results are recorded in the audit and are separate from full
hosted exact-head CI. The native report's twelve final source hashes, loader pin
and actual helper binary hash were independently checked.

The shared IPC implementation's behavior is unchanged. A separate local AMD64
Deck Progress positive/negative control also passed after its docstring update,
with four independently decoded SQLite snapshots; it predates the final Wine
receipt/probe edits and is not a full final-source native matrix.

No real Frame was contacted. Fresh ARM64 unload, compatibility-tool downloads,
install/remove through the real helper, a live Steam library, a real managed
Frame service, wearer-visible rendering and controllers remain unverified.
Existing ARM64 read-only-state evidence does not prove this new unload path.
