# Ludusavi child IPC EOF — 2026-11-01

Implementation `d3840f862a5935c10991cd4dd090daf46a3b8335`; base main `e02fb4fec61e169f4a8815ad82d872316cdb890f`.
Only store **103 / 1.2.2**, exact ZIP SHA-256
`8a69f45aadce763406b5c27bfef194761006d5e01c5e8841badeb13a27dd0d88`.
Published backend SHA-256
`00fcd7029ab4ba9fac0e872899a6dcadd6d05a8cc8892542b5abd2db967eac48`.

Reviewing #542's exact AMD64 artifact 13100869862 found an inherited Ludusavi
forced kill hidden behind Decky's zero parent exit. A committed red fixture
`bc5ed562c770038f5cc077d52000eefb1a06dc96` closes a real child IPC peer and signals only
the loader parent. It fails after **5.223926 seconds**:
one forced plugin kill, no original unload callback, parent exit zero.

The exact managed archive now receives the existing child-only IPC EOF helper
and a three-line prefix, followed by every original backend byte. The existing
bounded dependency-discovery repair is retained. Independent auditing
reconstructs all ten original archive members, the exact prefix and dependency
repair, and matches the added IPC helper. Frontend, manifest, flags and every
other original member remain unchanged. Existing installations need Update or
reinstall. Compatibility remains **partial**, and every other catalog row,
all 116 archive pins/policies/ratings and all 37 native cases are retained.
The installer/APPLY AST outside this added IPC block is unchanged.

Published Decky **3.3.0 native AMD64**, in a disposable container without network,
host devices or session access, verifies **three actual RPCs**: missing dependency,
fallback after a private dummy executable times out, and missing dependency after
restart. The timed-out executable is reaped. Replacing only the disposable
dependency helper with its published original reproduces its missing-version
failure; the IPC repair stays installed in this negative control.

All four parent-only unloads complete in
**0.214088 / 0.314339 / 0.214003 / 0.214093 seconds**.
Each observes the original plugin unload callback, zero forced kills or shutdown
errors, all exact owned process identities gone and successful adopted exits.
The first follows real IPC EOF. These explicit scoped stop assertions do not
claim a complete filesystem cleanup. The red observer included all container
processes in its reported dictionary; the final observer records just the owned
set. The ownership algorithm and shutdown assertions are retained.

All **32 native source fingerprints** match the implementation commit.
Full unit suite: **2005 tests**, **15 platform/optional skips**,
261.492 seconds. Disposable fake-Frame: **53 tests / zero skips**,
408.856 seconds, 116 exact archives: 69 install/removes and
47 expected refusals. Owned Compose resources were removed, prior image tags
restored, and the shared simulator identity/start/restart count/health retained.
The simulator log contains 0 unclosed HTTP socket ResourceWarnings.

Fresh publication-head hosted CI/e2e/native AMD64 and ARM64 and applicable
package checks remain required. ARM64 for this repair, actual Ludusavi
installation/backup/restore/cloud, save data, other command lifecycle,
native browser/backend integration, real Frame and worn/controller use are
**unverified**. Prior missing-dependency browser evidence used in-memory replies
and is not repeated here. No headset, security setting, schedule or PR #113 was
changed. No release is qualified. Other inherited forced-kill cases remain
separate work. JSON and compressed raw evidence retain the reports, consoles,
red/green fingerprints, full test logs, simulator cleanup and audit program.
