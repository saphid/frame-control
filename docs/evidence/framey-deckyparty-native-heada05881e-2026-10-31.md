# DeckyParty exact-head hosted audit — 2026-10-31

Audited PR #518 at unchanged head `a05881e798c4c63e4d60d719768a371afccddb90`,
which includes main `1ac29413186fb29d5844ee9ad1c5c6fd36eeac27`.
These are owned **uncommitted** audit files for a later documentation commit,
not part of that PR head. Source was not pushed and CI was not restarted.

## Native repair and negative controls

Both published Decky 3.3.0 artifacts from workflow 41201435838 independently
pass GitHub ZIP digest, exact successful job/checkout, 43-probe inventory,
34 published-archive pin, 16 source-fingerprint and 43 complete available console
hash checks. Inputs match locally tested integration source `713e1692`.
Both architectures verify 15 repaired and eight previous-managed RPCs, private
listing/download/upload/delete, refusal of missing/wrong credentials,
disable/restart, three controlled closed-peer reloads, unrelated-child survival
and final parent-only loader stops.

AMD64 repaired reloads take 0.368/0.368/0.367 seconds and final stop 0.215
seconds. ARM64 reloads take 0.363 seconds each and final stop 0.164 seconds.
No repaired reload kills the plugin or leaves its server. Previous-managed
controls reproduce a forced reload at 5.284/5.280 seconds; the server remains
until explicitly owned fixture cleanup. Their fresh-child final loader stops
exit zero. These negative outcomes do not qualify compatibility.

The production installer independently reconstructs the repaired backend,
unchanged IPC helper, exact receipt and all seven published nondirectory members.
The six files other than main.py remain byte-identical, and removing only the
IPC prefix gives the previous-managed backend's exact hash. Main's other
36 runtime branches, other 115 catalog rows, all 116 status/install policies
and the shared IPC adapter remain unchanged. TabMaster's current-main
backup/restore and negative controls pass 47/48 RPCs on both architectures.

## Hosted gates and limits

Both ownership artifacts from workflow 41201435825 pass exact checkout/digest,
14 source fingerprints, native two-way sync and strict source-bound Decky
service-shutdown checks. Raw peer-loader console/exit status is not separately
retained; no independent peer clean-shutdown claim follows.

At observation, the AMD64 signed-package mode from workflow 41201435952 passes
its actual package, complete guest packet, lifecycle/ownership and migration
audits. ARM64, browser HTTP and production-parent HTTP package jobs remain
running/queued. Each mode must be independently qualified when complete.

All ten general-check/PC jobs pass, with checkout
`322c62619c295454bdd5db8f98dc7d1112c7b71a` independently verified to have
exactly the PR head's tree. Hosted e2e passes 53 tests with one optional skip.
General platform suites and native PC tests retain documented skips.

The ARM64 positive matrix also retains forced kills for ProtonDB Badges,
SteamGridDB, Battery Tracker and Simple Timer. #523/#519/#521 already own the
latter three repairs. ProtonDB Badges needs investigation and a duplicate-work
check; no cause is established by this observation. AMD64 positive cases have
no forced kills in this artifact. Offline IP-discovery diagnostics and expected
negative controls remain; no global clean/error-free console claim is made.

Main's two package jobs are still running. No merge or release is qualified.
No LAN/HTTPS, real browser/panel/Steam CEF, managed real Frame, wearer/controller,
tagged installer or release proof was added. No headset or hourly schedule
was touched. Compatibility stays partial.

[Structured audit](framey-deckyparty-native-heada05881e-2026-10-31.json) and [raw reports/verifier source](framey-deckyparty-native-heada05881e-2026-10-31-raw.json.gz).
