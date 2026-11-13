# Game Theme Music: child IPC EOF and private settings shutdown

PR #561's exact head `7ddc04a7cc531cb8e404ceaa8d3633365987bdfb` failed its
native ARM64 primary gate in Game Theme Music, not in the plugin-job recovery fix.
The original backend completed discovery, private setting write/read and restart
readback, but its first stop required SIGKILL. Both loader parents returned zero.
The strict console gate correctly rejected this hidden unload failure.

The failed artifact ZIP SHA-256 and exact checkout were verified against the
producer log; all 44 retained source inputs match the exact PR head. The
[summary](framey-theme-music-ipc-eof-2026-11-06.json) records that job and artifact.
This is distinct from the Desktop Apps, DeckySpy and TabMaster repairs. No blind
retry or change to #561's job-recovery logic is needed for this failure.

Store 52 Game Theme Music 1.7.1-1 is pinned to archive SHA-256
`9ce293ab4db212c03c6b96dfbc5e4d92e874d33387463f53223773921f75a80e`.
Only that exact managed copy receives the existing child-local Decky 3.3.0 IPC
EOF adapter and its import prefix. Every remaining archive byte, including the
original media/settings methods and unload hook, is preserved. Existing copies
without the new shim receipt require explicit managed update/reinstall. A failed
update missing its helper preserves the installed copy and its private marker.
Compatibility remains partial.

Actual digest-pinned published Decky 3.3.0 in native AMD64 containers passes
private setting writes, an explicit child-peer EOF, a subsequent settings RPC,
two clean parent-only stops, original unload completion and restart readback.
Settings bytes stay identical across each stop; no recorded descendants remain
and an unrelated sibling survives. The exact original backend negative restores
only the pinned original main and removes the helper. The same peer EOF then
reproduces one forced kill and missing unload completion. That negative is an
expected failure, never a compatibility pass.

The fixture uses networkless, read-only containers with no host home, devices or
session sockets. It sends SIGTERM only to its owned loader, then reaps only its
recorded descendants. It does not kill plugin children to manufacture success.
Only private settings are exercised; no yt-dlp, search, media playback/download,
user library or Steam page patch is invoked.

[Compressed raw output](framey-theme-music-ipc-eof-2026-11-06-raw.json.gz) retains
source hashes, RPCs, settings snapshots, process identities and console hashes.
Local store/compatibility/runtime-inventory/IPC suites passed 116 tests without
skips. Fake-Frame e2e now asserts both installed source hashes and the receipt;
hosted e2e and repaired native ARM64 remain pending at this evidence capture.

Earlier unmodified setting readback evidence remains historical; it does not
establish clean shutdown. The separate in-memory browser settings replay was not
connected to this backend. Real Frame, wearer-visible panels, controllers,
search, downloads, playback and Steam game-page injection remain unverified. No
release is qualified by this isolated regression evidence.
