# Shotty child unload, 2026-10-31

Shotty remains **partial**. This repair applies only to managed official 0.1.0,
store ID 53, archive SHA-256
`ab7f6618b264a0cb766525e788cef6c3e1478c0fef98a701225e5e8af441e2fe`.
Update or reinstall an existing copy to receive the `shotty-ipc-eof` receipt.
The separate historical copy evidence in PR #498 does not qualify this unload.

Published Decky 3.3.0's child IPC listener repeatedly dispatches empty EOF without
yielding. On parent shutdown, the old managed Shotty backend passes its copy RPCs
but cannot finish async unload before Decky's five-second forced-kill deadline.
The repair installs the existing child-local IPC EOF adapter inside this exact
plugin. Its shared implementation behavior is unchanged; only its docstring
changes. No broad process cleanup or process-group signal qualifies shutdown.

The [baseline native report](framey-shotty-unload-baseline-2026-10-31.json)
records diagnostic source `7be700c9aab5556e1087cecdd13151f2620b7ed2`:
16 literal copy RPCs pass, but parent-only SIGTERM ends in one forced plugin kill
after 5.223 seconds. Loader exit zero alone did not qualify it.

The [repaired native report](framey-shotty-unload-2026-10-31.json) binds fourteen
source fingerprints to `21e58d4e570c36ff229832cf276ef83a9a07c3fc`. In a disposable
network-isolated native Linux AMD64 container, the pinned published Decky loader
discovered the managed plugin. The same sixteen RPC records passed unchanged;
one extra `was_rescued` read passed after restarting the loader. Two parent-only
SIGTERM stops returned zero in 0.214 seconds each, with the exact plugin children
gone, no forced kills or shutdown errors, and an unrelated sibling preserved.

Removing only the three-line IPC prelude recovers the exact previous managed
backend SHA-256 `5c62941c81887727b6f1ea2dbc0ba0c8c9e6153503ae3e3c234a4c4271d336de`.
That negative passes the same sixteen copy RPCs but again needs one forced plugin
kill. It is explicitly unqualified. The repaired backend SHA-256 is
`3941e3364b5e0e4b15c83c0ff66688671744e04c6b0d4f21923c33fc540bda51`.

The [independent audit](framey-shotty-unload-2026-10-31-audit.json) reconstructs
the exact production install block, verifies both managed backend hashes, all
unchanged published ZIP members, source and complete console hashes, process
identities, stop budgets and the unrelated sibling. It also verifies that the
other 115 catalog records are unchanged and the shared IPC behavior AST is
unchanged. Native runtime containers and private image tags were removed.

Eighty-four affected host tests passed. Filesystem copy tests deliberately stub
the IPC import; the published native loader supplies the actual IPC evidence.
The [fake-Frame result](framey-shotty-unload-e2e-2026-10-31.json) records a passing
pinned official-plugin HTTP/SSH install/remove test at source `21e58d4e`. Its
uniquely owned Compose containers, volumes, network and image tags were removed.
The final compatibility wording and evidence links were added afterwards;
the runtime product files did not change. These targeted runs do not qualify a
full exact-head hosted matrix.

No real Frame was contacted. Fresh hosted AMD64/ARM64 runs, the full forty-probe
native matrix, real Steam screenshots and notifications, continuous rescue,
real Frame installation, wearer-visible UI and controller interaction remain
unverified. Older ARM64 copy evidence cannot prove this new unload path.
