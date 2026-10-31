# ProtonDB IPC repair after the Simple Timer merge

Tested source: `7fc77589db970588f117ae8b794f0a53baaf2573`.
Normally merges main `4e1f664be47b99fcf88c84d1280126c39d6753b4` into the prepared
ProtonDB Badges repair and its original-negative assertion correction. No history
was rewritten. Adjacent-addition conflicts retain both exact archive dispatches,
the Timer/ProtonDB source fingerprints and both receipt regressions.

## Native controls

Isolated, networkless published Decky 3.3.0 AMD64:

- Repaired ProtonDB Badges 1.3.4: ten successful RPCs, post-EOF metadata response
  in 0.009 seconds and clean parent-only stops in 0.236/0.215 seconds. Zero
  forced-stop warnings; original unload completion, exact private settings,
  restart discovery and unrelated sibling preservation are verified.
- Original-source negative: six successful RPCs, the expected post-EOF timeout
  at 8.011 seconds and a forced stop at 5.224 seconds. This run records one
  forced-stop warning. Both earlier hosted failures and the separate local
  control record two; all remain explicit failed-shutdown verdicts. The
  [negative assertion correction](framey-protondb-negative-stop-warnings-2026-10-31.md)
  accepts either count only with successful owned cleanup. Positive clean-stop
  qualification still requires zero warnings.
- Newly merged Simple Timer: repaired/original/prior-managed controls retain
  31/10/18 RPCs and 30/14/24 events. Four repaired clean stops take
  0.215/0.265/0.214/0.225 seconds. Exact settings/deadline readbacks and original
  failure controls pass independent assertions.

Both reports bind the same 20 input hashes. Console hashes, owned process
identities, adopted child exits and private settings snapshots are independently
checked. The shared EOF adapter and exact published plugin archive are unchanged.
No original intermittent ARM64 failure cause is proved.

## Source and installer checks

The preservation audit verifies main's other 36 runtime bodies, all 115 other
complete catalog rows, all 116 status/install policies, other 33 positive native
cases, other installer branches and all main e2e assertions. The production
runner differs only by the ProtonDB helper fingerprint and original-source
negative control. Main's Timer helpers are byte-identical; the prior shared
stop helper and corrected negative assertion are retained.

Full server suite: **1,955 tests in 247.872 seconds**, successful with 16 existing
platform/optional skips. Website: **18/18**, no skips.

The single isolated HTTP/SSH installer test method passes all **37 pinned
fixtures**, including the merged Timer and ProtonDB receipt/backend/helper
assertions. Every fixture archive digest is rechecked. Owned Compose containers,
network, volumes, image tags and temporary configuration are removed; absence is
independently verified. This is not the full e2e suite or native full matrix.

[Audit record](framey-protondb-main4e1f664-refresh-2026-10-31.json).
[Raw native/unit/installer records and verifiers](framey-protondb-main4e1f664-refresh-2026-10-31-raw.json.gz).

This integration is prepared locally while the original remote head still has
live hosted checks. They must finish before its ordinary push. New exact-head
hosted CI/e2e/native AMD64+ARM64, every triggered package mode, current main and
feedback/mergeability remain required. There is no globally clean runtime claim.
No browser, badge rendering, real Frame, wearer/controller, tagged installer or
release pass is claimed. Headset, hourly schedules and pre-existing user data
were untouched; release remains held.
