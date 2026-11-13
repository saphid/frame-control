# Steamback integration with current main and TIME_WAIT repair

Tested source: `01634dbd25d9b508f9698d9a5a85003a4c47abf3`. Main `61efc562a65b552b1c00b75e8559c1c78764f57e` is its normal merge parent;
prior PR head is `83a7240b95cc7655a5bf48040ef905bc64c6229f`. The normal merge was conflict-free and retains
main's TIME_WAIT repair byte-for-byte. Whole-checker/installer/transaction-test AST audits preserve
main outside Steamback, including SteamGridDB, RadiYo TLS/receipt tests,
Prefix Manager's helper/catalog row/receipt tests and all other native cases.
All 25 native source inputs and shared IPC/console/timer helpers are preserved.

Local server: 1967 tests, 15 platform/optional skips.
Website: 18 tests, no skips. Resource warnings remain in raw logs.
Published digest-verified Decky 3.3.0 AMD64 executes nine cases: Steamback,
SteamGridDB and RadiYo repaired/original pairs and three Prefix Manager controls.
Independent Steamback 11/9 RPCs verify discovery, private save backup/restore/undo,
exact snapshots, source/other archive-member preservation, controlled-EOF
shutdown, original unload hook, restart and two clean parent-only repaired stops. The
original still reproduces its forced-stop failure. This fixture does not issue
an RPC between EOF and shutdown; its later responses come from the restarted
loader. Earlier evidence/PR summaries used broader "post-EOF response" wording;
that claim is not established by this Steamback fixture. Generic clean-runtime flags
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
Other historical native controls were not rerun locally; source preservation
is not execution. Fresh full hosted native gates remain required.

Isolated Fake Frame passes 53 tests, zero skips, in 401.237 seconds.
All 116 exact archives are mounted read-only. Every catalog install/refusal result
matches prior integration; this does not execute every official backend.
Owned containers, volumes, networks, image tags and temporary configuration are
removed. Independent readback preserves pre-existing simulator/image identities.

Prior exact head `83a7240b95cc7655a5bf48040ef905bc64c6229f` completed 18 checks in five workflows, with artifact
metadata retained. Those artifacts were not downloaded/audited this
pass. Their executions do not establish this combined source or eventual
evidence publication. Publishing this packet changes only evidence files.
Require exact publication-head CI/e2e/native AMD64+ARM64/ownership/every triggered
package mode, then fresh exact current-main/required-check/feedback/mergeability
gates. Current main still had five live checks at the initial read;
no PR was merged on that basis.

Separately, exact current main `61efc562a65b552b1c00b75e8559c1c78764f57e` completed hosted artifacts pass
fresh archive-digest/checkout/source audits: 50 native producer cases on each
architecture, six independent SteamGridDB/RadiYo/Prefix Manager behavior audits,
both ownership/runtime/user-service suites and 53 ARM64 e2e tests with zero skips
(346.617 seconds). This does not independently audit every native case or execute
every official backend. Real kernel TIME_WAIT recovery is 60.279s AMD64 and
62.966s ARM64; five classifier and eleven owned-unit tests pass per architecture.
Guarded state assertions remain source-bound producer checks; no independent raw
PID-state capture is retained. Hosted cleanup follows the successful source
trap/job; no independent post-job Docker-absence packet is retained. The first
local main audit wrapper still invoked previous PR533 audit programs. Its
mismatched report bindings were invalidated; correcting the executable paths
and rerunning all six audits against fresh main artifacts passed. The invalidated
attempt is retained separately, and is not accepted as main evidence.
Main's completed AMD64 signed-package artifact also passes independent signature,
two-way sync, strict service/migration shutdown, retained-data uninstall and
source/build-input binding checks. ARM64, browser HTTP and production-parent HTTP
package modes remain unqualified in this packet. These baseline
results do not substitute for the candidate's new exact-head hosted gates.

Compatibility remains partial. Real Steam saves, automatic game-triggered backups,
official UI, actual Steam CEF, managed Frame, worn visual/controller checks and
release smoke remain unverified. No real Frame or schedule was touched. Full
reports/logs/audits/verifiers are in the hash-bound gzip packet.
