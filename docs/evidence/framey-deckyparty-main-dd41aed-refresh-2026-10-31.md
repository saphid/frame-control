# DeckyParty with the Free Loader main repair, 31 October 2026

Local source `f53070412069a95879d8e1842ab5c0850372dea4` normally merges main
`dd41aede875d7a6b7abac68520784824b96103e9` into #518. Two conflicts in the
installer payload dispatch and native fingerprint inventory preserve both
DeckyParty's repair and main's Free Loader repair. No history was rewritten.
The local branch has not been pushed: three old-head package jobs remain live,
and pushing would cancel their evidence. Their results cannot qualify this source.

The independent source audit checks all 37 dispatch occurrences (32 distinct
conditions), preserving main's other 36 bodies and the prior DeckyParty body.
The other 115 complete catalog rows, all 116 status/install policies, shared
IPC adapter, console helper, archive inventory and Free Loader fixture match
main. Compatibility stays **partial**. All 17 native source fingerprints match
this source across the three local reports.

Published Decky 3.3.0 AMD64 runs in private isolated containers:

- DeckyParty: 15 repaired/eight prior-managed RPCs, authenticated private file
  operations and credential refusals, three repaired reloads in
  0.367/0.365/0.366 seconds, unrelated-child survival and final parent-only
  stop in 0.214 seconds. The prior-managed control force-stops after 5.279
  seconds and retains its server until explicitly owned fixture cleanup.
- Free Loader: 11 repaired/seven original-source RPCs, nonempty private
  settings/cache/hidden-state readbacks, exact byte preservation and restart
  persistence. Repaired parent-only stops take 0.214/0.259 seconds; the original
  source control requires a forced stop after 5.225 seconds. Exact owned
  descendants are reaped and an unrelated sibling survives.
- TabMaster: 47 repaired/48 original-source RPCs, successful valid-backup
  restore only with the repair, malformed/non-object refusals, preserved backup
  and per-user/shared settings across restart. Both parent-only stops complete.

Installer reconstruction verifies DeckyParty's seven published nondirectory
members and Free Loader's 19 entries including identical duplicates, exact
receipts, repaired backends, original-source hashes and unchanged IPC helper.
One production HTTP/SSH installer method passes all 37 pinned fixtures,
including both receipts/installed bytes/removal; it does not run official
backends or constitute the full e2e suite. All owned installer containers,
volumes, networks and image tags are removed, with absence checked.

The full server suite passes 1,947 tests with 16 skips; all 18 website tests
pass without skips. No focused suite was needlessly repeated. The full native
matrix was not run locally; its new expected inventory is 44 probes, 34 archive
pins and 17 source fingerprints. Native image/container cleanup is bound to
the runner; process cleanup and separate installer-resource absence are audited.

Exact main CI is still running/queued. Fresh pushed-head CI/e2e, native
AMD64/ARM64, ownership, PC and every triggered package mode remain required.
Offline IP-discovery diagnostics, TabMaster's expected JSON diagnostic and
expected negative failures are retained; no global error-free or clean-shutdown
claim follows. No LAN/HTTPS, browser/panel/Steam CEF, managed real Frame,
wearer/controller, tagged installer or release proof was added. No headset or
hourly schedule was touched.

[Structured audit](framey-deckyparty-main-dd41aed-refresh-2026-10-31.json) and [raw reports/logs/verifier](framey-deckyparty-main-dd41aed-refresh-2026-10-31-raw.json.gz).
