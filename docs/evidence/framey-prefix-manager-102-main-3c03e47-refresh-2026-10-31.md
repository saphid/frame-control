# Separate GitHub Prefix Manager 1.0.2 integration with current main

Verified on 2026-10-31T16:05:42.647659+00:00. PR #526 normally merges main `3c03e478a2fab181e6bdfe60ada6038663843ab3` into prior head `3a0fb45c8ebbb5cae68d71dda480a9fb3753f3b9`. Tested source: `ef46ca828f10b748c88ec8a62865b2f61f6e197a`. Later evidence-only changes must retain all 18 input fingerprints. Old-head package jobs are preserved until terminal before pushing.

The GitHub release remains separate from the live Decky store. Fresh public readbacks show store 130 serves **1.0.1**, SHA-256 `ef8c727943188cad04c63fae7e4e620b8080c07f35dec0c144e99c6166307473`. GitHub **v1.0.2**, asset 411464964, is 58,717 bytes with published digest `12ab420f06023cd13717489aa92a1babd09dec8566a601f4b4bb93464fbc92b6`, matching the tested fixture. GitHub 1.0.2 remains `unverified` in catalog lookup and is not offered as a store version.

## Fresh verification

- Independent baseline/candidate installation compares every live-store-1.0.1 installed file and receipt byte for byte. They are identical, with no new IPC adapter. All 116 catalog rows/policies and generated docs match main exactly.
- GitHub 1.0.2 retains its prior managed backend byte for byte below the EOF prefix, including actual-user paths, removed root request and bounded backup/delete safeguards. All other managed files are identical except the receipt and new helper; the helper matches the unchanged shared adapter.
- Published digest-verified Decky 3.3.0 AMD64 runs store 1.0.1 / repaired GitHub 1.0.2 / previous-managed negative through 39/42/40 literal RPCs. Independent state assertions verify backup bytes, old backups/outside marker preservation, user/library separation, symlink/traversal/duplicate-ID refusals and bulk-cleanup refusal.
- Repaired 1.0.2 answers after owned peer EOF, restarts and stops twice in 0.214/0.214 seconds with no forced kills, selected shutdown errors or remaining owned identities. Adopted exits are zero; backup ZIP hashes, outside marker and an unrelated sibling survive. The prior managed source reproduces a forced stop at 5.223 seconds. This published plugin has no custom unload hook: strict parent-only tests establish normal framework completion. The negative is not a compatibility pass.
- Free Loader repaired/original controls make 11/7 RPCs, preserve settings/deal snapshots and stop repaired children cleanly twice. Deck Settings repaired/previous-managed controls make 6/3 RPCs and run its original unload hook twice for the repair. Both old-source controls retain forced stops. Deck Settings rejects self-signed TLS before any HTTP request; actual uploads remain unverified.
- All three native reports share 18 fingerprints. Source/AST comparisons preserve main's other 36 dispatch bodies, other 33 native cases, every other installer branch/payload dispatch, the complete e2e file, shared IPC/console/inventory and Free Loader/Deck Settings fixtures. The prior Prefix Manager runtime body and lifecycle helper are unchanged.
- Full server suite: 1,948 tests, 16 platform/optional skips, no failures, 251.304 seconds. Website: 18 tests, no skips. Generated docs and diff checks pass.
- The production HTTP/SSH installer method passes all 37 pinned store transactions without skips. It covers live store 1.0.1, not GitHub 1.0.2 or official backend execution. Owned containers, volumes, networks and image tags are absent afterward, independently checked. Separate installation comparisons and native probes above cover GitHub 1.0.2.

## Evidence and limits

[Structured audit](framey-prefix-manager-102-main-3c03e47-refresh-2026-10-31.json) and [raw reports, public readbacks, logs and auditors](framey-prefix-manager-102-main-3c03e47-refresh-2026-10-31-raw.json.gz). Raw JSON SHA-256: `b24c5aa4eb0f38939839f66f8cd2a0471c4d33c798e6ce7288a34f91bb3b73ab`. Gzip SHA-256: `1367a31a6fd3cf5344395d1d883aaa11077364259dd851f9c55f7a1cd97b27e4`.

Only the three focused native cases ran locally, on AMD64. Full matrix and full e2e did not. Fresh final-head hosted CI/full e2e/native AMD64+ARM64/ownership/PC/every triggered package mode, completed exact current-main CI, feedback and mergeability remain gates. Expected full matrix: 45 probes, 34 positive archive pins, 18 inputs. Generic runtime-console clean-shutdown qualification stays false; no globally clean/error-free runtime claim follows.

Peer EOF reproduces one failure path; the earlier intermittent positive failure did not retain its socket history, so its sole cause is not proved. Earlier records remain historical in the [previous refresh](framey-prefix-manager-102-main-dd41aed-refresh-2026-10-31.md).

No refreshed browser integration, real Steam saves, managed Frame, wearer/controller, tagged installer or release proof. No real Frame, hourly schedule or pre-existing user data was touched. Release stays held until all exact release-commit gates and separately locked real Frame smoke pass.
