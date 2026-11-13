# SteamGridDB integration with the DeckyParty repair on main

## Announcement

SteamGridDB 1.8.1/store 36 retains its exact-archive child-IPC EOF repair after normally integrating current main, including merged DeckyParty repair #518. Published Decky 3.3.0 AMD64 verifies two clean SteamGridDB parent-only stops and private artwork/settings persistence; the original backend still reproduces forced termination. Compatibility remains **broken** because the Steam-only LibraryContextMenu frontend is unavailable. No Steam frontend, external artwork service, Frame, VR or release claim.

## Combined source

Original published PR [#523](https://github.com/saphid/frame-control/pull/523) head `e0613730c893ebf4fbc0b9708e73d7711e010dff` normally integrated main 7062ef4, then current main `de5eb65ff954381cec0df7b1f339f6916abee3d2` at tested source `66b9eb5348d44ee12140d76544f2465e83feeb87`. The second integration resolves adjacent regression declarations by retaining both SteamGridDB and DeckyParty controls, each with its own helper cleanup. Whole-checker/installer AST audits preserve current main outside SteamGridDB's prior repair, including all DeckyParty/TabMaster/Timer controls, other 36 runtime bodies and 33 native cases, other installer/e2e assertions, 115 complete catalog rows and all 116 rating/install policies. Mandatory full-catalog CI/cache/e2e files match main. All 22 native inputs bind the tested source; publication adds only this three-file evidence packet. No history rewrite.

## Verification

- Full combined-source server: 1963 tests, 15 platform/optional skips. Website: 18 tests, zero skips. Both pass. Earlier 1,962-test/18-site results belong to the source before the DeckyParty merge and remain historical.
- Published, digest-verified Decky 3.3.0 AMD64: ten native cases across SteamGridDB, TabMaster, Timer and DeckyParty share all 22 source hashes. SteamGridDB repaired/original completes 14/12 RPCs; repaired stops [0.186, 0.214] seconds, original forced-kill [5.224] seconds. Five private settings/artwork/VDF snapshots independently base64-decode, hash and match exact expected bytes before/after stop; settings survive restart. Independent exact installation preserves the published backend below the EOF prefix and every other archive member.
- TabMaster 47/48/47 and Simple Timer 31/10/18 RPCs retain settings/backup/restart behavior, positive original unload hooks and original/prior-managed negatives. DeckyParty repaired/prior completes 15/8 RPCs: three repaired reloads in [0.364, 0.364, 0.364] seconds have no forced kill or recorded old plugin/server survivors. Prior reload force-kills at 5.277 seconds and requires explicit owned fixture-server cleanup; its later clean replacement stop does not qualify that reload. Exact managed backend/adapter/receipt and original archive members verify independently. Unrelated siblings remain preserved. Generic runtime-console clean qualification remains false.
- Isolated Fake Frame: 53 tests in 401.346 seconds, zero skips. All 116 archive pins verify; 69 install/remove results and 47 refusals, including every reason, match the prior complete catalog run. This transport suite does not execute official backends.
- Independent cleanup verifies owned containers, volumes, networks, images and temporary config gone, with pre-existing simulator identity/start/restart count and shared image tags unchanged.

## Limits and remaining gates

This packet is local combined-source AMD64 proof. Earlier exact-head native AMD64/ARM64/package reports belong to the older published head. New published-head hosted full CI/e2e/native both architectures/ownership and all triggered package modes remain mandatory. Main's exact merge-commit CI must finish successfully, then fresh exact-main/head/checks/runs/required-check/feedback/mergeability gates must pass before merge. Existing socket/JSON diagnostics and every expected negative remain where recorded. No globally clean runtime, Steam LibraryContextMenu, renewed browser/frontend proof, external artwork service, actual Steam CEF, managed Frame, wearer/controller or release proof. No headset, schedules or pre-existing user data touched. Release stays held for all exact release-commit/tagged-installer/checksum/publisher/locked-Frame gates.

[Summary](framey-steamgriddb-mainde5eb65-integration-2026-10-31.json), [raw reports/snapshots/logs/verifiers](framey-steamgriddb-mainde5eb65-integration-2026-10-31-raw.json.gz), SHA-256 `ed931ec1ed29ec2117289637bfc678e627f2f89067ed6931295336d4cdaade94`.
