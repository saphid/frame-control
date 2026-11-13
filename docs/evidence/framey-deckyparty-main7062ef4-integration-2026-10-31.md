# DeckyParty repair integrated with current main

Tested source `1e08214b6624f7b4f0f14d67164e961ed5a110c2` normally merges main `7062ef4d81d7fa25e1562d22d0b1b92fa526b499` into PR [#518](https://github.com/saphid/frame-control/pull/518), prior head `1d4f64984aece0cc0b221dd41da28b2013000ddd`. The later publication commit changes only this evidence packet.

## Announcement

The exact DeckyParty File Manager 1.0.0/store 117 child-IPC repair retains three clean reloads with published Decky 3.3.0 AMD64 after the current-main integration. The old managed backend still reproduces its forced-kill reload. Compatibility remains **partial**. LAN, browser/panel, real Frame, wearer-visible and controller behavior remain unverified.

## Verification

- Whole-checker AST comparison preserves current main outside the prior DeckyParty changes, including TabMaster and Simple Timer controls. Installer, all other native cases, 115 other complete catalog rows, all 116 ratings/install policies and e2e assertions preserve main. The mandatory full-catalog CI/cache workflow and actual e2e script are byte-identical to main.
- Server: 1960 tests, 15 platform/optional skips. Website: 18 tests, no skips. Both suites pass.
- Published Decky 3.3.0 AMD64: eight native cases across DeckyParty, TabMaster and Simple Timer bind 21 source fingerprints to the tested source and pinned loader. Independent exact-archive installation/removal, managed backend/adapter bytes, receipt and unchanged archive members verify.
- Repaired/prior DeckyParty: 15/8 RPCs. Repaired controlled-EOF reloads finish in [0.365, 0.376, 0.379] seconds with original unload hooks, no forced kill, no old plugin/server survivors and an unrelated child preserved. Prior managed control takes 5.275 seconds, is forcibly killed and leaves an exact owned server needing fixture cleanup. Its clean replacement stop does not qualify the failed reload. Final parent-only stops: [0.214, 0.215] seconds.
- TabMaster: 47/48/47 RPCs preserve current managed/published-original/prior-managed controls, private settings, backup/restore, original unload hooks on positive stops and the expected forced-kill negative. Simple Timer: 31/10/18 RPCs preserve four clean positive stops, settings persistence and both negative controls.
- Isolated Fake Frame: 53 e2e tests in 399.247 seconds, zero skips, all 116 exact-digest catalog archives verified. Every record, outcome and reason is independently compared with the full catalog baseline; official backends are not executed by these transport/installer tests.
- Independent owned-resource cleanup verifies no owned containers, volumes, networks, images or temporary configuration remain. The pre-existing simulator identity/start/restart count and shared image tags are unchanged.

## Observed CI failure and limits

[#531 AMD64 native job](https://github.com/saphid/frame-control/actions/runs/41236913339/job/124642498607) at exact head `906bd32288cbdec7dbe1b7d6c158a4c7bf0b9bab` fails the old DeckyParty reload, waits for a missing unload hook, and times out. All its native inputs are byte-identical to main `7062ef4d81d7fa25e1562d22d0b1b92fa526b499`. This is retained as a repository/runtime failure, not called infrastructure or fixed by a blind rerun. Offline IP-discovery diagnostics and simulator socket ResourceWarnings remain in the raw logs.

This packet is local AMD64 combined-source proof. Historical hosted AMD64/ARM64/package evidence is a different head. New-head hosted CI, ARM64 and package qualification remain pending. Generic runtime-console clean-shutdown qualification stays false; scoped clean lifecycle checks do not imply a globally clean runtime. No release-commit, tagged installer or locked Frame smoke proof is claimed. No headset, schedules or pre-existing user data touched.

[Summary](framey-deckyparty-main7062ef4-integration-2026-10-31.json), [raw reports, logs and verifiers](framey-deckyparty-main7062ef4-integration-2026-10-31-raw.json.gz). Raw SHA-256: `d5be6953c6609468b5daa03201996d7fd610e8d54a2a7797fc54ea27bdc8ed12`.
