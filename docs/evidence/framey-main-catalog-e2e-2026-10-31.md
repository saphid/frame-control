# Exact-main Fake Frame e2e with the full catalog — 31 October 2026

The usual hosted e2e run at main
`6a5646e9da7f36ed45c840c3fe7190f2172e86ad` passed 53 tests with one optional
full-catalog test skipped because its archive cache was not mounted. A separate
local isolated run of that exact source passed **all 53 tests with zero skips**
in **392.363 seconds**.

The checkout was clean before and after execution; its Git tree was
`852411cf8d0e5103359ab89b45c466a9cc882984`. The JSON records 62 relevant source
fingerprints, the actual running container image IDs, runner and log hashes,
and all 116 ID/digest/outcome observations.

## Pinned inputs and scope

All 116 archive SHA-256 values came from this commit's
`ui/framey-compatibility.json`. Thirty-four archives were seeded from committed
fixtures; the remaining exact archives came from the public official CDN.
Every archive was hashed before static inspection and independently rehashed
after the run. Static inspection reported **zero errors**; it did not import or
execute plugin code. No live store metadata was read. The fixture preserves
the registry's store versions, including Games Prefix Manager 1.0.1; its
separate GitHub v1.0.2 asset is outside this catalog result.

The catalog case exercised actual Frame Control HTTP/SSH installer transport,
version/digest receipts, expected managed frontend bytes, removal and inventory
readbacks in a disposable Fake Frame:

- **69 installed and removed** successfully.
- **47 were refused** by the existing root, compatibility, architecture or
  archive policy, without a managed plugin remaining installed.

Every ID/digest/outcome matches the prior 30 October transport baseline.
Official plugin backends and Steam CEF were stubbed in this catalog case.
These outcomes do not establish plugin backend functionality, frontend controls,
real Frame operation or wearer-visible/controller usability. Compatibility
ratings and managed-install policy are unchanged.

## Runner and cleanup

The run used `scripts/framey-audit-fake.py` with two explicit orchestration
changes in an external temporary runner: point its source root at the clean
exact-main checkout, and replace the catalog-only unittest invocation with
`python3 -m unittest discover -v -s .`. The production sources, test bodies and
assertions were unchanged. The JSON records both the canonical and executed
runner SHA-256 values. This was a local run, not hosted CI.

The canonical helper created the unique project `framey-catalog-8e1e6d57be`.
Its host mounted the exact source and pinned cache read-only, with the normal
container-only e2e guard enabled. After success, it removed its two containers,
three named volumes and network. Independent Docker label queries found zero
owned containers, volumes or networks remaining. The existing shared simulator
was not selected or reset. The downloaded cache and raw proof files were
retained; no pre-existing cache or user data was deleted.

This closes the skipped catalog case for the tested source commit. All gates
must still be satisfied at any eventual release commit, including exact main
CI, package/native results, tagged installers, checksums, publisher checks and
the locked wearer-safe real Frame smoke test. This record publishes no release.

[Compact results and source fingerprints](framey-main-catalog-e2e-2026-10-31.json).
