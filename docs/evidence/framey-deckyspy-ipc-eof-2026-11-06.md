# DeckySpy child IPC EOF and clean shutdown

The exact main commit `04b9f8a93d884eb7d67f0fbe105fb1e7464599c3`
failed its native AMD64 job because DeckySpy required SIGKILL. Decky returned
zero, but the original `=== Unload Decky Spy ===` hook never ran. The failed
artifact ZIP and its source bindings were checked against that exact commit.
This was not a Windows-transfer failure or sufficient evidence of an infrastructure flake.

DeckySpy is store 89, version 0.6.7, archive SHA-256
`2d431a89826ed5cf3fd37258373eb3b46c841c39795aa8b25f83e59f4eee87c7`.
Only that managed archive receives the existing child-local Decky 3.3.0 EOF
adapter. Its psutil wheel, battery fallback and original statistics-thread and
unload-hook code stay intact. No loader-wide transport change is made.

The ordinary local main probe happened to pass. The new native negative control
therefore explicitly closes a child IPC peer after the metrics/settings RPCs.
It restores the previous managed backend body, verified by SHA-256, retaining
psutil and battery adaptations. It then reproduces one forced kill and the
missing original unload hook. This is an expected regression, not a compatibility
pass or an unmodified-upstream test.

With the adapter, actual digest-pinned Decky 3.3.0 on native AMD64 passes metrics,
private setting commit, explicit peer EOF, two clean parent-only stops, restart
and statistics-thread readback. Both stops run the original unload hook, preserve
exact private settings bytes and leave no recorded descendants. An unrelated
sibling survives. The container has no network, devices, host home or session
sockets. Only its owned loader receives SIGTERM; the fixture does not kill plugin
children to manufacture success.

The [summary](framey-deckyspy-ipc-eof-2026-11-06.json) records timings and all source
hashes. [Compressed raw output](framey-deckyspy-ipc-eof-2026-11-06-raw.json.gz)
retains discovery, RPCs, process identities, settings snapshots and console hashes.
The store, compatibility, runtime-inventory and IPC suites passed 114 tests.
The fake-Frame e2e assertion now checks both installed backend and adapter hashes;
its hosted execution and native ARM64 execution remain pending at this evidence capture.

Existing copies without the EOF receipt require explicit update/reinstall.
Earlier read-only real-Frame/browser evidence remains limited to that earlier
backend. No real Frame, wearer-visible UI, controller, alerts or audio verification
was performed for this repair. No release is qualified by this evidence alone.
