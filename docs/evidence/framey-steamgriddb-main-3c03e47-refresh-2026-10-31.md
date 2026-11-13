# SteamGridDB integration with the Deck Settings main update

Verified on 2026-10-31T15:46:26.618331+00:00. PR #523 normally merges main `3c03e478a2fab181e6bdfe60ada6038663843ab3` into prior head `e5406d6cc97105af2d043931465e9a302a7576bb`. The tested source is `f0e569d3b5294789b2c4ed2f1721f5dc08249c4f`. This record does not qualify a later head until all 18 input fingerprints and the diff are checked.

SteamGridDB stays **broken**: the Steam-only LibraryContextMenu frontend remains unavailable. This repair addresses a reproduced child IPC shutdown failure; private backend calls are not headset usability evidence.

## Fresh verification

- The published, SHA-256-verified Decky 3.3.0 AMD64 loader discovers exact SteamGridDB 1.8.1/store 36, archive `e84f5b1f111af8862b06218479491fbf61036e1bfd9f16f93f9901e9b9ebc5e0`.
- Repaired/original controls make 14/12 literal API1 RPCs. The repaired controlled-peer-EOF and restarted ordinary stops complete in 0.225/0.235 seconds with no forced kill. The original backend reproduces its forced stop at 5.226 seconds. The negative is not a compatibility pass.
- Each SteamGridDB stop independently rereads five private files before and after shutdown. Base64 decoding, SHA-256 and exact byte comparisons verify settings, signed shortcut IDs, the unselected VDF canary and PNG artwork. Owned descendants disappear, adopted children exit zero, and an unrelated sibling survives.
- Free Loader repaired/original controls make 11/7 RPCs. The repair stops cleanly twice at 0.235/0.214 seconds, preserving settings/cache and hidden-state changes. Its original negative retains the forced stop.
- Deck Settings repaired/previous-managed controls make 6/3 RPCs. The repair stops cleanly twice at 0.214/0.185 seconds and runs its original unload hook. The previous managed negative retains its forced stop. The installed HTTP method rejects self-signed TLS before the fixture receives any request; real uploads remain unverified.
- All three native reports carry the same 18 SHA-256 input fingerprints. The source audit preserves main's other 36 runtime dispatch bodies, every other exact installer branch and payload dispatch, the other 115 catalog rows, and all 116 status/install policies. Deck Settings, Free Loader, shared IPC and console fixtures match main.
- An independent installation compares the exact SteamGridDB backend prefix and helper against source and preserves every other published archive member byte for byte.
- Full server suite: 1,951 tests, 16 platform/optional skips, no failures. Website: 18 tests, no skips. Generated compatibility documentation and diff checks pass.
- The production HTTP/SSH installer method passes all 37 pinned fixtures with no skips. This includes the SteamGridDB delivered backend/helper SHA-256, receipts, frontend bytes and removal. All owned containers, volumes, networks and image tags are absent after cleanup and independently checked.

## Evidence

The [structured audit](framey-steamgriddb-main-3c03e47-refresh-2026-10-31.json) and [compressed raw reports, logs and auditors](framey-steamgriddb-main-3c03e47-refresh-2026-10-31-raw.json.gz) retain the results. Raw JSON SHA-256: `47c029ac34a5275e70f8869ad2344d424ec2ff3b8f12f9017e663ea0360a9fda`. Gzip SHA-256: `45bb0724d1d7767007c65fe0eaf7e0a126380cf9026121e62e1f14a5fa166849`.

Earlier hosted AMD64/ARM64 observations and the original failure remain historical in the [previous refresh](framey-steamgriddb-main-dd41aed-refresh-2026-10-31.md). They were not rerun or used to qualify this head.

## Limits and remaining gates

Only the three scoped native cases ran locally on AMD64. The expected hosted full matrix has 45 probes, 34 positive archive pins and 18 inputs. Full e2e, native AMD64/ARM64, PC, ownership, all triggered package modes, completed exact current-main CI, mergeability and unresolved feedback still gate merging. Scoped lifecycle results do not prove globally clean plugin shutdown; negative controls intentionally retain forced kills. The peer history of earlier ARM64 failures is unknown.

There is no browser, LibraryContextMenu, external artwork service, actual Steam CEF, managed Frame installation, worn visual/controller, tagged installer or release proof. No real Frame, hourly schedule or pre-existing user data was touched. Release stays held pending every exact release-commit gate and the separately locked real Frame smoke test.
