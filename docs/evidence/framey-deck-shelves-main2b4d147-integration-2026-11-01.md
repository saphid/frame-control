# Deck Shelves integrated with Steamback main

Tested source `3e4b3f10c0b92bed58dfb3ffd2a712ba0446ae80` normally merges previous PR #528 publication `41930bac738da3ef8e7fe749779a82ca4bf166f2`
and main `2b4d1474ec71573ab91845b46e21f773284bebad`. Three conflicts in runner/checker/store tests were resolved
by retaining both complete Shelves and Steamback controls. Whole-module AST
audits ran before staging/commit. They preserve main's checker and installer
outside Shelves, complete main store tests plus the three prior Shelves methods,
Steamback helper/probe/installer/receipt/e2e controls, DNS/TIME_WAIT repairs,
other 115 catalog rows, all 116 status/install policies and all 26 native inputs.

Local Linux server: **1,971 tests**, 15 platform/optional skips; website:
**18 tests, zero skips**. Published digest-verified Decky 3.3.0 AMD64 executes
**11 cases** across Shelves, Steamback, SteamGridDB, RadiYo and Prefix Manager.
Five independent behavior/installation audits pass. Shelves 4/3 RPCs preserve
private settings/backup bytes, JSON, hashes and metadata, verify original unload
hooks, clean parent-only shutdown and restart, and reproduce original forced
termination. An unrelated sibling survives. RPC after EOF and before shutdown
was not exercised; post-restart RPC was verified. Generic runtime-wide clean
shutdown flags remain false; expected negative diagnostics are retained.

Steamback 11/9 RPCs retain private save/undo snapshots and restart state;
SteamGridDB 14/12 RPCs retain artwork/VDF/settings/IPC (status remains broken);
RadiYo 9/7 RPCs retain both self-signed TLS rejection paths and HTTP/IPC;
Prefix Manager 39/42/40 RPCs retain bounded backup/delete and outside markers.
The initial Prefix audit adapter expected the sole changed probe to be Battery
Tracker. Correcting that expectation to Shelves allowed the audit to finish;
all Prefix behavior assertions are unchanged. Initial program/log/result and
corrected program/log/result are retained. The live store was not requeried:
store 130 stays exactly **1.0.1**. The separate GitHub 1.0.2 ZIP digest
`12ab420f06023cd13717489aa92a1babd09dec8566a601f4b4bb93464fbc92b6`
retains compatibility lookup status **unverified**. Both exact archive install
outputs and receipts remain byte-identical to main.

Isolated Fake Frame: **53 tests, zero skips**, 408.349 seconds.
All 116 cached exact archive hashes and all install/refusal outcomes match prior
integration. This suite does not execute every official backend. Independent
cleanup verifies owned containers, networks, volumes, images and config absent;
the shared simulator and pre-existing image identities are preserved. Socket
resource warnings remain in the raw logs.

This packet records source and local executions before publication. Publication
adds only this note, summary and compressed packet. Previous-head hosted results
do not qualify this integration. Require fresh exact-publication CI/e2e/native
AMD64+ARM64/ownership/all triggered package modes, then exact green current main,
required checks, unresolved-feedback/review and mergeability gates before merge.
Compatibility stays partial. Actual Steam CEF, Steam Home/official UI, managed
Frame and worn visual/controller behavior remain unverified. No real Frame,
schedule, PR #113, pre-existing data or security settings were changed. No release.

Raw SHA-256: `ac46f16d19ba533c6d880526236cd7f2aee655a0992a8ab1429f33853430417c`. Full reports, logs and verifier sources are retained.
