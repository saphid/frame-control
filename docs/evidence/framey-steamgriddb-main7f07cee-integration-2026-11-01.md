# SteamGridDB integration with RadiYo main

Tested source `b644e6c9b22f5a449e7cb41a1dda2aeefd01d121` normally merges current main `7f07cee953f0be340f98239ddcaeb02117b87fc4` into
prior PR head `845c874dafac55fbaf755863e3387a2b63388672`. Three conflicts retain both adapters, both native
negative controls and separate helper removal for each control. Whole-checker,
installer and transaction-test AST audits preserve main outside SteamGridDB,
including RadiYo's TLS/receipt tests and Prefix Manager's helper and policies.
All 24 native input hashes bind to the executed combined source.

Local server: 1964 tests; 15 platform/optional skips.
Website: 18 tests, zero skips. Resource warnings remain in raw logs.
Digest-verified published Decky 3.3.0 AMD64 executes fifteen fixture cases.
Six independent audits verify SteamGridDB 14/12 RPCs, RadiYo 9/7,
Prefix Manager 39/42/40, TabMaster 47/48/47, Simple Timer 31/10/18 and
DeckyParty 15/8. Private artwork/settings/VDF bytes, scoped backup/delete,
restart, clean parent-only repaired stops and original forced-stop controls
remain distinguished. RadiYo retains both self-signed TLS rejection paths.
Both Prefix Manager versions install byte-identical files/receipts to main.
Store 130 remains 1.0.1; GitHub 1.0.2 ZIP
`12ab420f06023cd13717489aa92a1babd09dec8566a601f4b4bb93464fbc92b6`
remains unverified in the compatibility lookup. The live store was not queried.

Isolated Fake Frame passes 53 tests with zero skips in 400.592s.
All 116 version/digest-pinned archives are mounted read-only; per-plugin
install/refusal results match the prior main integration. This transport test
does not execute every official backend. Independent cleanup verifies owned
resources absent and pre-existing simulator/image identities unchanged.

Prior exact head `845c874dafac55fbaf755863e3387a2b63388672` passed 17 checks; Windows server tests failed.
GitHub reports: The hosted runner lost communication with the server. Anything in your workflow that terminates the runner process, starves it for CPU/Memory, or blocks its network access can cause this error.
The job logs returned HTTP 404; the failure cause is not established. That
failure is retained, not reclassified as success. All prior-head native/e2e,
ownership and four package modes are audited separately, including nine
successful artifact/job/step bindings and 1,369 source-hash bindings across
152 distinct paths. Those older executions do not execute this integration.
Fresh publication-head CI/e2e/native AMD64+ARM64/ownership/every package mode
and exact current-main/feedback/mergeability gates remain mandatory.

Compatibility remains broken because the official Steam LibraryContextMenu
is unavailable in the isolated Framey panel. Official UI, actual Steam CEF,
managed real Frame, wearer-visible/controller usability and release smoke
remain unverified. No real Frame, schedule, PR #113, security settings or
pre-existing data were changed. Full logs/reports/audits/verifiers are in
the raw gzip, bound by the summary hash. No release is qualified.
