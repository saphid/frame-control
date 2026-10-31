# Non-Steam Badges actual-user shortcut mappings

The exact official 0.1.0 ZIP for store 133 has SHA-256 `9c12b21fd02da12f4c37f9aab68d75172a11787d09c3478f15b4fc97e01df131`. Its published backend hard-codes `/home/deck/.steam/steam/userdata` in three places. An actual Decky 3.3.0 replay at source `e69ddff72c515c8f5123a9ad8e0eff432b90ab3e` discovered the unmodified plugin but returned an empty mapping despite five valid synthetic shortcuts under `/home/tester`. The [original failure](framey-nonsteam-badges-original-path-failure-2026-10-30.json) retains that failed run and its limits.

Managed installation changes only those three paths to the service user's home. It requires both the exact archive digest and original backend SHA-256 `af524b89f765018281f07aa2dd557a69d862a9c9ec3df0b5eb3c489e96ed2704`. API1, manifest, every other archive member and license remain byte-identical. The shim is `nonsteam-badges-user-paths`; existing copies need update/reinstall. A different store ID/archive receives no adaptation.

A network- and device-isolated native AMD64 replay at source `787f9d9db0e90b52a9ae74bec87b0640d0efa30b` passes five repaired RPCs and three unchanged-original negative RPCs. The original still returns no mappings. The repaired backend reads synthetic GOG/Epic/Amazon/Luna and unknown-store entries, normalizes a signed app ID, skips a missing app ID, returns empty for malformed VDF without rewriting it, and reads the same mapping after a loader restart. Only one synthetic numeric Steam account is present. The binary VDF is written independently by the fixture; no real Steam data is mounted.

The [audit](framey-nonsteam-badges-user-paths-2026-10-31.json) verifies all seven source fingerprints, pinned published loader/archive/backend hashes, exact RPC results, every other archive member and all four parent-only zero-exit loader stops with PID/start-time reaping observations. Both complete retained loader consoles were inspected; neither has a JSON decode shutdown diagnostic or the checked shutdown exception markers. An error-free console is not claimed: expected missing-file/malformed-input diagnostics are retained. Disk and process observations remain source-bound without a full container/process snapshot. The runner cleans its owned containers, volumes and image tag.

A focused owned fake-Frame replay also passes managed installation, exact adapted-backend digest and shim receipt, partial compatibility status, and removal. Its test and cleanup exit zero; an independent check finds none of its containers, volumes or image tags. This is install/remove coverage, not browser or native RPC evidence.

Non-Steam Badges stays **partial**. Active Steam account selection, frontend/backend integration, Steam-page badge injection, ARM64, a managed Frame installation, wearer-visible UI and physical controllers remain unverified. Live search is not exercised; the upstream search method retains its existing `ssl._create_unverified_context` behavior unchanged. No public request or system security change was performed. No real Frame, active user session, hourly schedule or pre-existing data was touched.


## Current-main refresh

The branch normally merged main `358e423a62300689543e2083d5213af763c03a46`
at frozen source `372c75b0f099f4ef58697a6450829468163fefe2`, after all original
workflows and package audits completed. Those earlier CI results are historical
and do not qualify the refreshed head. The [refresh audit](framey-nonsteam-badges-main358-refresh-2026-10-31.json)
and [native replay](framey-nonsteam-badges-main358-native-2026-10-31.json)
retain the fresh AMD64 observations: five repaired RPCs, three unchanged-original
negative RPCs and four parent-only zero-exit stops. The merged Bluetooth fixture
also passes its 13 RPCs with results matching current main. All seven runtime
inputs match the frozen source. The 59 store, 17 compatibility and three runtime
coverage tests pass; all 116 catalog policies and the other 115 complete records
match current main. Both owned images and their ancestor containers are absent.

Fresh exact-head CI, ARM64, full e2e and every triggered package variant remain
required before merge. This refresh adds no Steam-page badge, active-account,
live-search, real Frame, wearer-visible or controller claim.

## Startup-gate refresh onto main 6a5646e

The previous head `7565cee074c8fa576a2853b94372726dc7a21de1` completed
17 of 18 checks successfully. Its production-parent HTTP signed-package job
`124394464439` failed: `bwrap` reported the missing shared Flatpak runtime
`tmp` path before sync. Artifact `13025316289` and the failure packet were
independently audited; this failed gate was not rerun unchanged. The precise
path-removal actor and timing remain unproven.

Normal merge `2d3b10348f726005ebca26329449d169632addd1` brings in main
`6a5646e9da7f36ed45c840c3fe7190f2172e86ad`, including #506's serialized
private-peer readiness and #499's bounded unreachable-network retry. The
startup probe is byte-identical to main. All seven native-runtime source
fingerprints are unchanged from the previous head; the other 115 complete
catalog records and this plugin's version, digest and partial rating are
preserved. All 120 focused store, compatibility, native-coverage, package-gate
and fetch tests pass locally (13.405 seconds).

Previous hosted native, ownership, e2e and passing package results remain
historical. The refreshed head requires fresh full hosted qualification,
including both native architectures and every triggered package variant.
No real Frame was contacted, and no wearer-visible or controller check was
performed. This refresh does not establish the failed package path as fixed.

## Refresh onto main 8ebe9ac

Normal merge `3ae2c60845840ca9f64fa67ceadc58f01d2b78f5` incorporates main
`8ebe9acda1cb1174120f07fb42b39afcc1ed8c9c`, including the PC keyboard shortcuts
and exact Deck Progress IPC EOF repair. Conflicts preserve both independent
plugins' positive and unchanged-original negative cases. The keyboard page,
server and IPC helper are byte-identical to main. All 116 version/digest/status/
installer policies and the other 115 complete compatibility records are preserved.

The [refresh evidence](framey-nonsteam-badges-main8ebe-refresh-2026-10-31.json)
retains fresh local AMD64 published Decky 3.3.0 observations at that frozen source:
five repaired and three original Non-Steam RPCs, four zero-exit parent-only stops,
and both complete consoles. The Deck Progress positive and original cases also
pass: 36 RPC results, four independently decoded SQLite snapshots, no forced
plugin kill for the repair and the expected two forced kills for the original.
All eight runtime fingerprints per report match the frozen source. Both unique
runner images and their ancestor containers are absent. The 60 store tests,
17 compatibility tests and three native inventory tests pass locally.

Prior full hosted qualification at `6339489` is historical. This refreshed head
requires fresh native AMD64/ARM64, full e2e, ownership and every triggered package
mode, plus exact current-main/feedback/mergeability gates. No real Frame, badge
injection, browser/backend integration, active Steam account, live search,
wearer-visible view or controller check was performed. No release is published.

## Refresh onto main dd12031f

The prior head `d8aac9de3e796fb9ff7a6c0a68e67f5bf6b24ab3` failed AMD64
ownership job `124443207697`: its raw-peer probe still found the helper after
loader shutdown. That failed head was not rerun unchanged. Normal merge
`9db3c6c5da68b9505c3fb7b8391e5e59556c1f75` incorporates current main
`dd12031f55ccbcba01aa07296080495df1935af1`, including #508's owner-death
repair and Ludusavi discovery. Additive conflicts retain both plugin cases.

The [fresh audit](framey-nonsteam-badges-maindd12031-refresh-2026-10-31.json)
qualifies that frozen source locally on AMD64: 131 focused tests pass;
Non-Steam Badges retains eight exact repaired/original RPCs, four parent-only
zero-exit stops, private-file preservation and both complete console hashes.
Deck Progress retains 36 RPCs and four independently decoded SQLite snapshots;
Ludusavi retains three literal results, bounded slow discovery, its original
failure and four parent-only zero-exit stops. All nine fingerprints per native
report match the merged source. All 116 catalog version/digest/status/install
policies and the other 115 complete records match main.

The actual Syncthing raw-peer boundary also passes with a freshly built,
source-verified helper and eleven Rust ownership tests: two-way sync, restart,
authenticated Decky HTTP reads, API-key refusal, helper disappearance and owned
process reaping. This older runner signals the loader process group and does
not retain complete successful peer/Decky consoles or establish a clean loader
exit. The prior failure's full cause remains unproven; #513 owns the stricter
evidence gate. This does not qualify a Syncthing installer or service manager.

The isolated fake-Frame pinned-official install/remove test passes. Its owned
containers, volumes and network are absent, as are ancestor containers for all
four local native/runtime images. Fresh final-head hosted AMD64/ARM64, full
e2e, ownership and every package mode remain required. No real Frame, browser
badge injection, active account selection, live search or controller check was
performed, and compatibility stays partial.

## Current main Wine Cellar integration, 2026-10-31

Main `51841728090a45f9f452b4cd4ccf93f4caf8df14` was merged normally into the
previous head `1016d0729866d7809f9925a716c4409ebb63f759`, producing frozen source
`447d0445806557a20cc272e74582898aab7442ad`. The additive native-runner conflict
retains both the Non-Steam original-path negative and Wine Cellar's prior-source
unload negative. The Wine backend, compressed backend, IPC adapter and lifecycle
helper match current main exactly. All catalog rows except Non-Steam match main;
Non-Steam's complete record and exact archive remain unchanged from this PR.

The [source-bound audit](framey-nonsteam-badges-main5184172-refresh-2026-10-31.json)
records 91 passing focused host tests and targeted local native AMD64 checks.
All twelve source fingerprints per report match the frozen source. Non-Steam's
eight repaired/original literal RPC records, four parent-only zero-exit stops,
private shortcut preservation, exact published-member hashes and complete
consoles pass independent verification. Wine Cellar retains two clean parent-only
stops with its exact helper reaped, then reproduces the prior-source zombie and
forced plugin kill in the explicitly unqualified negative control.

The pinned official-plugin HTTP/fake-Frame SSH install/remove test passed at the
same source. Its uniquely owned containers, volumes, network and image tags are
absent; targeted native containers and private image tags were also removed.
Subsequent commits add this evidence only. Earlier hosted passes remain tied to
their earlier heads: the refreshed final head still requires fresh complete
CI/e2e, ownership, package modes and native AMD64/ARM64 qualification. The full
native inventory now contains 41 probes and 34 published archive pins, with
twelve source fingerprints; the targeted local replay does not qualify that
full matrix. No real Frame or visible Steam badge behavior was tested.

## Refresh onto Shotty main

Main `1c1e4f588735dc3119f67f90ca8c33d3a90563cd` was merged normally at tested source `3e4e5f93451de458a1a1f5c7f472dee428d4d30e`. The Non-Steam implementation diff is unchanged. All other 115 complete catalog records, shared IPC implementation, Wine runtime sources, Shotty helper and both published archives match current main. All 31 existing main native probe bodies remain identical at AST level; the additional probe is Non-Steam’s private shortcut case. Compatibility stays partial.

All 79 focused host tests pass (18 compatibility, 61 store), as do generated docs, diff checks and coverage of 34 declared native cases. No new local native run is claimed after this refresh. Fresh exact-head CI/e2e, native/runtime/package evidence, exact current-main CI and final integration/feedback/rules review remain gates.

The previous head `392b81162d6d0ec9842d5c0f5cb4823601403804` completed all 18 checks and five triggered workflows. Its independently audited native AMD64/ARM64 evidence retains 41 probes, 34 published archive pins and 12 source fingerprints per architecture. All four package modes now pass immutable-digest, job/checkout, source and full guest-result audits; twelve HTTP/production-parent captures were visually inspected and bound to ZIP members. The production-parent warning remains visible and names below its iframe viewport are not claimed visible. These results qualify the named historical head only.

[Source and historical-artifact audit](framey-nonsteam-badges-main1c1e4f5-refresh-2026-10-31.json), [focused host log](framey-nonsteam-badges-main1c1e4f5-refresh-2026-10-31.log). Existing raw-peer shutdown evidence limits remain: strict private-service shutdown passes, but the older raw-peer runner lacks complete successful-console/clean zero-exit qualification. Browser badge injection, active Steam account selection, integrated browser/backend behavior, real Frame and wearer/controller usability remain unverified.
