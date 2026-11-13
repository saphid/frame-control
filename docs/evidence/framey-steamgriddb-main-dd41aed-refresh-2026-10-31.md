# SteamGridDB refresh against main dd41aed

This refresh normally merges main `dd41aede875d7a6b7abac68520784824b96103e9`
into SteamGridDB PR #523 at tested source
`01dbbcf945ecb45c536174fe4a298a43cea6ad9b`. The single conflict was the
installer's exact-archive helper dispatch; both SteamGridDB and main's Free
Loader dispatch remain. No history was rewritten. Evidence-only commits after
this source must retain its 17 native input hashes.

The [structured audit](framey-steamgriddb-main-dd41aed-refresh-2026-10-31.json)
and [raw records and auditors](framey-steamgriddb-main-dd41aed-refresh-2026-10-31-raw.json.gz)
bind the local tests to those inputs. Native published Decky 3.3.0 runs use
disposable networkless AMD64 containers and private Steam-shaped data only:

- Repaired SteamGridDB makes 14 literal API1 RPCs. Its controlled-disconnect
  and ordinary restarted stops take 0.214 and 0.185 seconds, without forced
  plugin kills. Five private settings/artwork/VDF files retain independently
  decoded bytes and hashes across each stop. The original backend makes 12
  RPCs and reproduces a forced stop in 5.225 seconds; this is a negative control.
- Main's repaired Free Loader makes 11 literal RPCs and stops cleanly twice
  in 0.225 seconds each. Its private settings/cache bytes and hidden-state
  transition survive stop/restart. The original source makes seven RPCs and
  reproduces a forced stop in 5.223 seconds.
- Both cases verify recorded descendants disappear, adopted children exit
  zero and an unrelated sibling survives. Only the loader receives the stop
  signal. Owned Unix-peer EOF is a controlled reproduction; the original
  historical ARM64 peer history is unknown.
- One production HTTP/SSH installer method covers 37 pinned fixtures,
  including exact receipts/backend/helper bytes and removal. It does not run
  official backends or replace full e2e. Owned containers, volumes, networks
  and image tags are independently absent after cleanup.

The full server suite passes 1,949 tests with 16 optional/platform skips; all
18 website tests pass without skips. AST comparisons preserve main's other
36 runtime bodies, every other installer
branch, all main helper dispatches, the other 115 complete catalog rows and all
116 status/install policies. Shared IPC, console collection, official archive
inventory and the Free Loader fixture match main. The full native matrix now
expects 44 probes, 34 positive archive pins and 17 input hashes; only the two
scoped native cases above ran locally.

Separately, old-head `a68e13c2091c014b37cea234123c8ae9cfdeddc4` hosted AMD64
and ARM64 artifacts from run `41197855325` were audited against GitHub digests,
successful exact-head checkout logs, 43 probes, 34 archive pins and 16 source
hashes per architecture. Both repaired SteamGridDB cases stop cleanly twice and
retain the five private files; both original-source negatives force-kill once.
Those results do not qualify this refreshed head. Positive Battery Tracker
forced stops remain unrelated observations owned by PR #519; other retained
JSON diagnostics also prevent a globally clean runtime claim.

Fresh exact final-head CI, full e2e, native AMD64/ARM64, ownership, PC and all
triggered package modes remain required. Current main must finish all gates
before any merge. SteamGridDB remains **broken** because the Steam
LibraryContextMenu frontend is unavailable in Framey. No browser, external
artwork service, actual Steam CEF, managed real Frame, wearer-visible UI,
physical controller or release proof was obtained. No headset, hourly schedule
or pre-existing user data was accessed.
