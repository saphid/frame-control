# GitHub Prefix Manager 1.0.2 after the Simple Timer merge

Tested source: `0dcb4b1b4521a1cc6ba9f5badeffd2319734784c`.
Normally merges main `4e1f664be47b99fcf88c84d1280126c39d6753b4` into the prepared
Prefix Manager integration. No history was rewritten. Two adjacent-addition
conflicts retain both exact archive dispatches and all native source fingerprints.

## Store and GitHub remain separate

Fresh public store metadata still identifies store 130 as **1.0.1**, digest
`ef8c727943188cad04c63fae7e4e620b8080c07f35dec0c144e99c6166307473`.
GitHub's separate **v1.0.2** asset is 58,717 bytes with published SHA-256
`12ab420f06023cd13717489aa92a1babd09dec8566a601f4b4bb93464fbc92b6`.

Independent installation comparison preserves every store-1.0.1 file and receipt
byte-for-byte against this main. GitHub 1.0.2 adds only the scoped EOF prefix,
shared helper and corresponding receipt change to the previous managed backend.
All existing user-path and bounded backup/delete safeguards remain. Its catalog
lookup remains **unverified**; it is not represented as the live store version.
The published plugin has no custom unload hook.

## Fresh native and merge controls

Published Decky 3.3.0 AMD64, networkless disposable containers:

- Store 1.0.1: 39 RPCs.
- Repaired GitHub 1.0.2: 42 RPCs; two normal framework stops in 0.164/0.214
  seconds, with owned identities reaped and no forced kill. Backup hashes,
  outside marker and unrelated sibling survive.
- Prior-managed 1.0.2: 40 RPCs and the deliberate forced-stop negative. This is
  a reproduced failure, not a compatibility pass.
- Newly merged Simple Timer: repaired/original/prior-managed controls retain
  31/10/18 RPCs and 30/14/24 events. Four repaired stops take
  0.214/0.225/0.185/0.214 seconds. Exact settings/deadlines and expected negatives
  pass independent assertions.

Both reports share all 20 exact input fingerprints. All available console hashes
are verified. All 86 focused store/compatibility tests pass, with no skips.
The source audit preserves main's other 36 runtime bodies, every other installer
branch, all 116 complete catalog rows and install policies, all other 33 positive
native cases, main's e2e assertions and the shared EOF adapter. Only the previously
reviewed Prefix Manager branch/helper/control differs from main.

The earlier full suite (1,948 tests, 16 optional/platform skips), 18 website tests
and 37-fixture HTTP/SSH installer run belong to the prior prepared integration;
they were not rerun as full suites for this merge. Their
[historical evidence](framey-prefix-manager-102-main-3c03e47-refresh-2026-10-31.md)
remains available. The new hosted final-head full CI/e2e/native AMD64+ARM64 and
all triggered package modes remain required. Native focused controls and source
preservation do not replace those gates.

[Audit and public readbacks](framey-prefix-manager-102-main4e1f664-refresh-2026-10-31.json).
[Raw native/focused logs and verifiers](framey-prefix-manager-102-main4e1f664-refresh-2026-10-31-raw.json.gz).

No full local matrix, refreshed browser, real Steam saves, managed Frame,
wearer/controller or release proof is claimed. Headset, hourly schedules and
pre-existing user data were untouched. No globally clean runtime claim follows;
other repairs retain their own gates. Release remains held.
