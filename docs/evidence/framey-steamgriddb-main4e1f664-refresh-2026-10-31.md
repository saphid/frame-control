# SteamGridDB integration after the Simple Timer merge

PR #523 normally merges main `4e1f664be47b99fcf88c84d1280126c39d6753b4` into prior head
`d82c94be2568682f833cd0a61bc3c34dd1f736ff` at tested source `3707de522012e545c840c40ae09a03ec8a941558`.
The sole conflict was adjacent exact-archive payload dispatches; both SteamGridDB
and Simple Timer branches are retained. No history was rewritten.
SteamGridDB stays **broken** because its Steam-only LibraryContextMenu frontend
has no target in the isolated Framey panel. This repair and its private backend
fixtures do not establish frontend usability. Existing copies need Update/reinstall.

## Fresh local verification

Published, digest-verified Decky 3.3.0 AMD64 discovers store 36 SteamGridDB 1.8.1,
archive `e84f5b1f111af8862b06218479491fbf61036e1bfd9f16f93f9901e9b9ebc5e0`.
Repaired/original controls run **14/12 RPCs**. Controlled peer EOF and restarted
ordinary repaired stops complete in **0.214/0.215 seconds**, with no forced kill,
recorded identities reaped, zero adopted exits and unrelated sibling preserved.
The original-source control reproduces a **5.234-second forced stop**.
That expected negative is not a compatibility pass and does not prove the
unretained peer history of an earlier hosted failure.

Every stop independently rereads five private files. Exact decoded bytes,
SHA-256 and parsed contents verify settings, signed shortcut IDs, an unselected
VDF canary and PNG artwork before/after shutdown. Independent installation
reconstructs the original published backend beneath only the EOF adapter prefix,
verifies the delivered helper, and preserves all other published archive members.

The merged Simple Timer control runs **31/10/18 RPCs**, preserving events,
settings snapshots, restart state and the original state failures. Four repaired
stops complete in **0.206/0.195/0.214/0.215 seconds** with original unload
hooks and no forced kill; the previous managed forced stop remains an expected
negative. Both native reports match all **20 source fingerprints**.

Full server suite: **1,952 tests**, **16 platform/optional skips**,
no failures, in **251.020 seconds**. Website: **18 tests**, no skips. One isolated
production HTTP/SSH installer method passes all **37 pinned fixtures**, including
exact SteamGridDB/Timer receipts and delivered backend/helper bytes. Owned
containers, volumes, network and image tags were removed; absence was checked
independently. This method does not execute every published backend.

Source/AST audits preserve main's other 36 runtime bodies, other 33 native cases,
other 115 complete catalog rows, all 116 status/install policies, every other
installer/payload dispatch, non-SteamGridDB e2e assertions, shared adapter and
current Timer helpers. The prior SteamGridDB lifecycle probe/helper are unchanged.
Generated compatibility docs and diff checks pass.

## Limits and remaining gates

Previous full-native/hosted results and Free Loader/Deck Settings native controls
remain historical; they were not rerun for this refresh. Their current source
bodies/helpers are retained. Scoped lifecycle results do not qualify globally
clean plugin shutdown. Full native matrix and full e2e did not run locally.
Exact final pushed-head hosted CI, full e2e, native AMD64/ARM64, applicable PC,
owned-watchdog and every triggered package mode, completed exact current-main
CI, feedback and mergeability remain mandatory.

No browser, LibraryContextMenu, external artwork service, actual Steam CEF,
managed Frame install, worn visuals, controller, tagged installer or release
proof is claimed. Headset, hourly schedules and pre-existing user data were
untouched. Release remains held until every exact release-commit gate and
locked real Frame smoke passes.

[Structured audit](framey-steamgriddb-main4e1f664-refresh-2026-10-31.json) and [raw reports, logs and verifiers](framey-steamgriddb-main4e1f664-refresh-2026-10-31-raw.json.gz).
