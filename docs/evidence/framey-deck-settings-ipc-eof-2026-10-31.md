# Deck Settings IPC disconnect and unload, 31 October 2026

Deck Settings 1.2.6 can require a forced plugin stop after its Unix IPC peer
disconnects. This is a controlled local reproduction: the ordinary stop on
current main was clean. It does not establish the cause of an earlier hosted
ARM64 forced stop.

The repair applies only to store ID 93's pinned archive, SHA-256
`23c2a933a6883e2622f0184c33a76ce4a4e88c0a7dcd730f9bab71b8c3702132`.
It installs the existing child-local EOF adapter after verifying the previous
managed backend hash. The existing upload TLS repair and shared adapter are
unchanged. Older managed copies require Update or reinstall. Compatibility
remains **partial**; all 116 catalog status/install policies are preserved.

At source `fa726ad4734c564db66c516bcaf28e9ddb6e68ad`, published Decky 3.3.0
AMD64 discovered the production-managed plugin and returned six RPC results
across a restart: read-only vendor/storage queries and `add(17, 25) == 42`.
The fixture closed one owned Unix peer before the first stop and signalled
only the loader parent. The repaired plugin ran its original `Goodnight
World!` unload hook and stopped without forced kills or shutdown errors in
0.225 seconds. After restart, an ordinary stop took 0.185 seconds. Recorded
descendants disappeared, adopted children exited successfully, and an
unrelated sibling survived both stops.

A negative case removed only the new IPC prefix/helper, retaining the existing
TLS repair. The same controlled disconnect required a forced stop after
5.196 seconds and did not run the original unload hook. A separate pre-repair
run at `dc443fb7eafce71dccdda42545360bcd82070648`, with the production
installer identical to main, reproduced the forced stop after 5.224 seconds.
Both final cases rejected a private self-signed HTTPS endpoint before any
HTTP request; no real upload or credential was used.

The full server suite passed 1,944 tests with 16 skips; the website suite
passed all 18 tests without skips. The 88 focused installer/compatibility
tests passed without skips. Two new
assertions failed before the repair. The raw evidence retains an initial
test-path error and its corrected passing run. One production HTTP/SSH
installer test passed across all 37 pinned fixtures, including receipt,
installed backend/helper hashes and removal for Deck Settings. It does not
execute all official backends or constitute the full e2e suite. Owned Compose
resources and baseline containers/images were removed and their absence
checked.

The independent audit checks all 16 native source fingerprints, preserved
archive members, the unchanged TLS implementation and shared adapter, 36
other runtime branch bodies and 115 other catalog rows. It uses CPython
3.13's reviewed AST printer to compare the native TLS-method hash from the
Debian fixture with the host's Python 3.12 source tree; the printers have
different default handling of empty fields.

[Audit JSON](framey-deck-settings-ipc-eof-2026-10-31.json) records hashes,
timings and limits. [Raw evidence](framey-deck-settings-ipc-eof-2026-10-31-raw.json.gz)
contains the verifier, full native console reports, pre-repair runs, focused
logs and installer execution/cleanup records.

Fresh exact-head hosted CI/e2e, native AMD64/ARM64, PC/package and exact-main
gates remain required. The full native matrix was not run locally. No real
Frame, browser change, upload/report/settings write, Steam session, worn
visual/controller test or release was performed. The historical ARM64 failure
cause remains unproven.
