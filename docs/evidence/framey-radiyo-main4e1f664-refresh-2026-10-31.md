# RadiYo current-main refresh with retained TabMaster hold

**Merge remains held until #525 qualifies the recorded TabMaster shutdown failure.**
The earlier positive case force-stopped at 5.225 seconds and did not complete
its first unload hook. RPC/backup-restore success did not waive the strict failure.
That exact historical report, console/hash and failed audit remain retained.
No new TabMaster check runs here; its current repair is owned by #525.

PR #520 normally merges main `4e1f664be47b99fcf88c84d1280126c39d6753b4` into prior head `3bfccea94b5cdd13de055901d7dee47edc8f2002`
at tested source `955ce6dba2497a2eeecc139672941c328c15e5df`. Four conflicts retain RadiYo and main's Free Loader,
Deck Settings and Timer installer/tests/helpers. The older Timer receipt test is
replaced by main's current three-receipt assertions. No history rewritten.
Compatibility stays **partial**; existing RadiYo copies need Update/reinstall.

## Fresh local verification

Digest-verified published Decky 3.3.0 AMD64 discovers exact store 24 RadiYo! 1.3,
archive `647111578aa7a5ecd16af8d7fe6c068a6d7ea8737c6dce5ac2d52e84a549ec43`. Repaired/previous-managed controls complete
**9/7 RPCs**. Both fetch and redirect methods reject self-signed HTTPS. Loopback
HTTP body/header and redirect checks survive restart. Two repaired parent-only
stops take **0.225/0.215 seconds**, without forced plugin kills, selected stop errors
or recorded owned survivors. Adopted exits are zero; an unrelated sibling
survives. The prior managed TLS backend force-stops at **5.234 seconds**.
Its negative remains a failed-shutdown verdict.

Independent installation reconstructs the previous verified-TLS backend from
the exact published archive, checks its bytes beneath only the EOF prefix,
the unchanged shared helper and every other unmodified published member.

Current-main Simple Timer completes **31/10/18 RPCs**, retaining settings,
events, restart state and original/previous-managed negatives. Four repaired
stops take **0.185/0.225/0.215/0.246 seconds**. Both native reports match
all **20 source fingerprints**. Scoped lifecycle results do not establish global
clean/error-free runtime; generic console qualification remains false.

Full server suite: **1,950 tests**, **16 platform/optional skips**,
no failures, **267.215 seconds**. Website: **18 tests**, no skips. One isolated
production HTTP/SSH installer method passes all **37 pinned fixtures**. Exact
receipts/backend/helper/removal assertions pass; owned containers, volumes,
network and image tags are removed and absence independently checked. This
method does not execute official backends or replace full e2e.

Complete checker/runner/installer AST audits preserve main's other 36 runtime
bodies, other 33 native cases, other 115 complete catalog rows, all 116 policies,
other installer/payload/e2e/compatibility assertions and current Timer helpers.
RadiYo's prior probe, strict lifecycle helper, negative, exact installation
and TLS repair remain unchanged. Generated docs/full-range diff checks pass.

## Limits and remaining gates

The historical TabMaster failure is not a passing current-head result and is
not waived by these scoped controls. #525 qualification remains mandatory.
Earlier full-native, ARM64, browser and Free Loader/Deck Settings controls remain
historical, not rerun here. Full native matrix and full e2e did not run locally.
Fresh exact final-head CI/e2e/native AMD64+ARM64/applicable PC/ownership/every
triggered package mode, completed current-main CI, feedback and mergeability
remain required. Peer-loader raw consoles/exit status are not independently
retained here; reported native process cleanup is separately audited.

No external station, trusted HTTPS, audio playback, refreshed browser, actual
Steam CEF, managed Frame, wearer/controller, tagged installer or release proof
is claimed. Headset, schedules and pre-existing data untouched. Release remains
held until all exact release-commit gates and locked real Frame smoke pass.

[Audit](framey-radiyo-main4e1f664-refresh-2026-10-31.json) and [raw reports, historical failure, logs and verifiers](framey-radiyo-main4e1f664-refresh-2026-10-31-raw.json.gz).
