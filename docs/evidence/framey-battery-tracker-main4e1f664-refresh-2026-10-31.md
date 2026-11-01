# Battery Tracker integration after the Simple Timer merge

PR #519 normally merges main `4e1f664be47b99fcf88c84d1280126c39d6753b4` into prior head `228ac14b3ef8ebfc0d9d2ed17c36ac4af560b35e`
at tested source `8def91f2b5205ea669ba407d33a28adba9d8513a`. The two conflicts retain both Battery Tracker
and Simple Timer installer dispatches and native fingerprints. Compatibility
stays **partial**; existing managed copies need Update/reinstall.

## Fresh local verification

Digest-verified published Decky 3.3.0 AMD64 discovers exact store 67 Battery
Tracker 0.2.0, archive `91c388d3c1b52079314045b79671ad55c767510658b6193f6936ed6cad383b94`.
Repaired/previous-managed controls complete **38/36 RPC observations**; polling
counts can vary. Repaired parent-only stops take **0.215/0.214 seconds** without
forced plugin kills, selected stop errors or recorded owned survivors. Adopted
children exit zero and an unrelated sibling survives. Pending private battery
samples flush to SQLite, survive restart and grow at the next flush. Both final
SQLite snapshots are independently base64-decoded, hashed, integrity-checked
and compared with exact SQL rows. The previous managed source takes
**5.224 seconds**, needs a forced kill and loses its pending samples.

Independent installation preserves the prior managed backend beneath only the
EOF adapter prefix, preserves other published files outside existing backend
and manifest changes, and retains the exact unchanged shared adapter. Existing
root-request removal and actual-user battery-supply mapping stay intact.

Current-main Simple Timer completes **31/10/18 RPCs** with persistent settings,
events, restart state, original-source and previous-managed negatives. Its four
repaired stops take **0.214/0.215/0.235/0.214 seconds** without forced kills.
Both native reports match all **20 source fingerprints**. Scoped lifecycle
assertions do not establish a globally clean or error-free runtime.

Full server suite: **1,950 tests**, **16 platform/optional skips**,
no failures, **250.043 seconds**. Website: **18 tests**, no skips. One isolated
production HTTP/SSH installer method passes all **37 pinned fixtures**, including
Battery Tracker/Timer receipts and delivered backend/helper bytes. Owned
containers, volumes, network and image tags were removed and absence independently
checked. This method does not execute all official backends or replace full e2e.

Whole-checker/source/AST/catalog audits preserve main's other 36 runtime bodies,
other 33 native cases, other 115 complete catalog rows, all 116 status/install
policies, every other installer/payload/e2e branch, shared adapter and current
Timer helpers. Battery Tracker's prior probe, private helper and top-level
negative are unchanged. Removing only Battery Tracker's exact additions
reconstructs main's complete runtime checker and runner. Generated docs and
full-range diff checks pass. Three pre-existing historical evidence files in
the original worktree remain byte-identical; their stale outer gzip hash is
excluded from this refresh.

## Limits and remaining gates

Earlier hosted/full-native and Free Loader/Deck Settings/TabMaster controls
remain historical, not rerun here. #525 owns the prior TabMaster unload failure;
successful backup/restore is not clean-shutdown proof. Full native matrix and
full e2e did not run locally. Fresh exact final-head CI, full e2e, native
AMD64/ARM64, applicable PC, ownership, every triggered package mode, completed
exact current-main CI, feedback and mergeability remain mandatory. Peer-loader
raw consoles and exit status are not independently retained here.

No new browser/panel, real battery, long-term recording, Steam CEF, managed
Frame, wearer/controller, tagged installer or release proof is claimed.
Headset, hourly schedules and pre-existing user data were untouched. Release
stays held until every exact release-commit gate and locked real Frame smoke passes.

[Structured audit](framey-battery-tracker-main4e1f664-refresh-2026-10-31.json) and [raw reports, logs and verifiers](framey-battery-tracker-main4e1f664-refresh-2026-10-31-raw.json.gz).
