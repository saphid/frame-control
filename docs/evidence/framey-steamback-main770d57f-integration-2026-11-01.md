# Steamback integration with SteamGridDB main

Tested source: `4927d66646f3bae15159bdb80fa62127914768b2`. Main `770d57fd228786ee410a72e477f948805a928b11` is its normal merge parent;
prior PR head is `bb14eb4b3b64ea9e6da6b888b59b8c54c295dd82`. The sole installer conflict retains both
exact-archive adapters. Whole-checker/installer/transaction-test AST audits preserve
main outside Steamback, including SteamGridDB, RadiYo TLS/receipt tests,
Prefix Manager's helper/catalog row/receipt tests and all other native cases.
All 25 native source inputs and shared IPC/console/timer helpers are preserved.

Local server: 1967 tests, 15 platform/optional skips.
Website: 18 tests, no skips. Resource warnings remain in raw logs.
Published digest-verified Decky 3.3.0 AMD64 executes nine cases: Steamback,
SteamGridDB and RadiYo repaired/original pairs and three Prefix Manager controls.
Independent Steamback 11/9 RPCs verify discovery, private save backup/restore/undo,
exact snapshots, source/other archive-member preservation, post-EOF response,
original unload hook, restart and two clean parent-only repaired stops. The
original still reproduces its forced-stop failure. Generic clean-runtime flags
remain false; expected negative diagnostics remain recorded. All save data is
owned and private; no person's real Steam saves were used.

Independent SteamGridDB 14/12 RPCs retain private artwork/VDF/settings byte
readbacks, source preservation, post-EOF response and repaired/original unload
behavior. Its compatibility stays **broken** because official UI/context-menu
support is unverified. RadiYo 9/7 RPCs retain both self-signed TLS rejection
paths, private HTTP fetch/redirect, restart and repaired/original unload behavior.
Prefix Manager 39/42/40 RPCs retain scoped backup/delete, outside markers and
restart. Independent current-main/combined-source installations produce byte-
identical files and receipts for store 1.0.1 and GitHub 1.0.2. Store 130 remains
pinned to 1.0.1; GitHub candidate ZIP
`12ab420f06023cd13717489aa92a1babd09dec8566a601f4b4bb93464fbc92b6`
remains unverified in compatibility lookup. The live store was not queried again.
The initial standalone RadiYo verifier accidentally selected ID 25 instead of 24
while updating its input-count assertion. It failed before installation; corrected
verifier rerun passed on the same unchanged native report/source. Failed audit
attempt is retained in the raw packet. Other historical native controls were not rerun locally; source preservation
is not execution. Fresh full hosted native gates remain required.

Isolated Fake Frame passes 53 tests, zero skips, in 402.778 seconds.
All 116 exact archives are mounted read-only. Every catalog install/refusal result
matches prior integration; this does not execute every official backend.
Owned containers, volumes, networks, image tags and temporary configuration are
removed. Independent readback preserves pre-existing simulator/image identities.

Prior exact head `bb14eb4b3b64ea9e6da6b888b59b8c54c295dd82` completed 18 checks in five workflows, with nine
artifacts retained in metadata. Those artifacts were not downloaded/audited this
pass. Their executions do not establish this combined source or eventual
evidence publication. Publishing this packet changes only evidence files.
Require exact publication-head CI/e2e/native AMD64+ARM64/ownership/every triggered
package mode, then fresh exact current-main/required-check/feedback/mergeability
gates. Current main was still running four package jobs at the initial read;
no PR was merged on that basis.

Compatibility remains partial. Real Steam saves, automatic game-triggered backups,
official UI, actual Steam CEF, managed Frame, worn visual/controller checks and
release smoke remain unverified. No real Frame or schedule was touched. Full
reports/logs/audits/verifiers are in the hash-bound gzip packet.
