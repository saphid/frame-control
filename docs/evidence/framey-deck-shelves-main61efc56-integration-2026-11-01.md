# Deck Shelves integration with current main and TIME_WAIT repair

Tested source: `790febb2c265f0eee4e2142a39695b6307d4dc4c`. Normal merge parents are prior PR head
`8c42a972abcc816e365235c31f37aa85f6b7ae71` and main `61efc562a65b552b1c00b75e8559c1c78764f57e`. The merge was conflict-free. Source audits preserve
main's TIME_WAIT repair byte-for-byte, complete installer/checker/test modules
outside Deck Shelves, other 115 catalog rows, all other native cases/probes,
shared IPC/console/timer helpers and all 25 native source fingerprints.

Local server: 1968 tests, 15 platform/optional skips.
Website: 18 tests, no skips. Resource warnings remain in raw logs.
Published digest-verified Decky 3.3.0 AMD64 executes nine fixture cases: Deck
Shelves, SteamGridDB and RadiYo repaired/original pairs plus three Prefix Manager
controls. Four independent audits pass. Deck Shelves 4/3 RPCs verify discovery,
private settings writes/readbacks, original unload hooks, two clean parent-only
stops and restart. Settings/backup bytes, hashes, parsed JSON and file metadata
remain identical. An unrelated sibling survives. The original backend reproduces
forced termination and missing unload hooks. Independent exact-archive install/
remove checks preserve every other published member and verify the receipt.
The fixture closes IPC before shutdown and verifies RPC responses after restart;
it does not issue an RPC between EOF and shutdown. Generic clean-runtime flags
remain false; expected negative diagnostics remain recorded. This establishes
private backend lifecycle, not Steam Home injection or wearer-visible behavior.

SteamGridDB 14/12 RPCs retain private artwork/VDF/settings bytes, post-EOF response
and repaired/original unload behavior; its status remains **broken** because
official UI/context-menu support is unavailable. RadiYo 9/7 RPCs retain both
self-signed TLS rejection paths, private HTTP fetch/redirect and restart/unload.
Prefix Manager 39/42/40 RPCs retain bounded backup/delete, outside markers and
restart. Store 1.0.1 and GitHub 1.0.2 install files/receipts byte-identical to main.
Store 130 remains pinned to **1.0.1**. Separate GitHub 1.0.2 ZIP
`12ab420f06023cd13717489aa92a1babd09dec8566a601f4b4bb93464fbc92b6`
remains **unverified** in compatibility lookup. The live store was not requeried.
Other historical native controls were preserved by source audits, not rerun
locally. Fresh full hosted native gates remain mandatory.

Isolated Fake Frame: 53 tests, zero skips, 402.550 seconds. All
116 exact catalog archives are mounted read-only; every install/refusal result
matches prior integration. This suite does not execute every official backend.
Independent cleanup confirms owned containers/volumes/networks/images/config
absent and pre-existing simulator/image identities unchanged.

Previous exact head `8c42a972abcc816e365235c31f37aa85f6b7ae71` completed all 18 checks in five workflows with
no review feedback. Those executions do not execute this integrated source or
its evidence publication. No old-head artifacts were downloaded/audited this
pass. Publication adds only this packet, summary and note. Require exact new-head
CI/e2e/native AMD64+ARM64/ownership/all triggered package modes, then fresh exact
main/required-check/feedback/mergeability gates before merging.

Separately, fresh exact-main AMD64, browser-HTTP and production-parent-HTTP package artifacts pass
GitHub archive digest/checkout, source/build-input bindings, signed two-way sync,
strict service/migration shutdown and preserving uninstall audits. The browser
fixture uses Chromium, actual Decky RPC and the production HTTP dispatcher;
actual Steam CEF and managed Frame remain unverified. ARM64 remains unqualified in this baseline snapshot. These
main-only results do not qualify the candidate or a release.

Compatibility stays partial. Steam Home injection, official UI, actual Steam CEF,
managed Frame, worn visual/controller behavior and release smoke remain
unverified. No real Frame, schedule, PR #113 or pre-existing data was changed.
Full reports, logs and verifier sources are in the hash-bound compressed packet.
