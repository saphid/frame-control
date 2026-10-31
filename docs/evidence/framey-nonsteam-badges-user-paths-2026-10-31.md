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
