# ProtonDB integration with current main and TIME_WAIT repair

Tested source: `dbcaa5ab7bd25e76399ebb1c2e3983a5e7c7083d`. Main `61efc562a65b552b1c00b75e8559c1c78764f57e` is its normal merge parent.
The final normal merge retains main's TIME_WAIT repair and the ProtonDB adapter. All 25
native source fingerprints remain present. Independent whole-checker/installer
AST audits preserve main outside ProtonDB. Complete current-main store/receipt
test modules remain preserved outside exact prior ProtonDB additions, including
all Prefix Manager tests. Other native probe bodies/cases, shared adapter/console
helpers, timer helpers and full-catalog CI remain preserved. The shared stop
helper adds only an optional marker with the identical Free Loader default.

Local server: 1970 tests, 15 platform/optional skips.
Website: 18 tests, no skips. Resource warnings remain in raw logs.
Digest-verified published Decky 3.3.0 AMD64 executes eleven cases: ProtonDB,
Free Loader, SteamGridDB and RadiYo repaired/prior controls plus three Prefix Manager cases.
Independent ProtonDB 10/6 RPC audits verify discovery, private settings bytes,
post-EOF response, restart, two parent-only clean stops and original unload hooks.
The original negative retains the RPC timeout/forced-stop warnings and completed
owned cleanup. Historical intermittent ARM64 socket failures remain failed
observations; their cause is not proven. Exact archive/receipt/install/removal
and untouched published members verify. Independent Free Loader 11/7 RPC audits
preserve the shared helper's default, private persistence, clean repaired stops
and deliberate original forced kill. Generic clean-runtime flags remain false;
expected negative diagnostics remain recorded. This proves private lifecycle
fixtures, not badge rendering or headset usability.

SteamGridDB 14/12 RPCs retain private artwork/settings/VDF bytes, post-EOF
response, owned restart and repaired/original shutdown. Its compatibility remains
broken because official UI/context-menu support remains unavailable.

RadiYo 9/7 RPCs retain both self-signed TLS rejection paths, HTTP fetch/redirect,
restart and repaired/prior-managed unload behavior.

Prefix Manager 39/42/40 RPCs retain scoped backup/delete, outside markers and
restart. Current-main/combined-source installations produce byte-identical files
and receipts for store 1.0.1 and GitHub 1.0.2. Store 130 remains pinned to 1.0.1;
GitHub ZIP `12ab420f06023cd13717489aa92a1babd09dec8566a601f4b4bb93464fbc92b6`
remains unverified in compatibility lookup. The live store was not queried again.
Preparing the standalone RadiYo verifier introduced a wrong plugin ID when
updating the native source-input count. The first audit failed before checking
behavior; the next failed on its still-old source-count assertion. Correcting
the ID to store 24 and count to 25 passed against the same unchanged source and
runtime report. Both failed attempts and verifier sources are retained in the
raw packet. Production source and tests were not changed by these corrections.

Other native controls were not rerun locally; source audits preserve their probe
bodies/cases and helpers. Fresh full hosted native gates remain required.

Isolated Fake Frame at prior source `14a9b4a5b425a53aa08e1195385d94e5c8f1cf4f`
(main770d integration): 53 tests, zero skips, 405.190 seconds.
That run finished before integrating main61ef. It is not execution of the final
combined source. Server and all eleven selected native cases were rerun after
the final integration; exact-publication-head hosted e2e remains mandatory.
All 116 exact catalog archives are mounted read-only. Every install/refusal
result matches prior main integration; this does not execute every backend.
Owned containers, volumes, networks, images and temporary configuration are gone.
Independent cleanup confirms pre-existing simulator/image identities unchanged.

Prior exact head `022c35bec1c384c0dca67bfb60869c50e6895867` completed all 18
checks in five workflows. Metadata is retained; old-head artifacts were not
downloaded/audited this pass. Those runs do not execute this combined source or
its eventual publication. Publishing adds only three evidence files. Require
fresh exact-publication-head CI/e2e/native AMD64+ARM64/ownership/every triggered
package mode, then current-main/required-check/feedback/mergeability gates.

Compatibility stays partial. Badge rendering, official UI, actual Steam CEF,
managed Frame, worn visual/controller behavior and release smoke remain
unverified. No real Frame or schedule was touched. Full reports, logs, audits
and verifier sources are in the hash-bound compressed packet.
