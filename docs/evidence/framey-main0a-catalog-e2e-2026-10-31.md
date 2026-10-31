# Full-catalog e2e after the keyboard merge — 31 October 2026

Exact main `0a91fc6bbdd5b11f48b08bf7e7f5374d67a3c40c`, including the
keyboard modifier/chord fix, passed **all 53 isolated Fake Frame e2e tests
with zero skips** in **392.150 seconds**. This is a local regression run,
separate from the hosted e2e job and the
[earlier main6a run](framey-main-catalog-e2e-2026-10-31.md).

The checkout was clean before and after the run; its exact Git tree was
`a1b6ceb3d33efee94612fabdbf260553987cdf66`. The
[machine-readable evidence](framey-main0a-catalog-e2e-2026-10-31.json)
records 64 relevant source fingerprints, live Docker input hashes, actual
container image IDs, runner/log hashes and every catalog outcome.

## Catalog inputs and results

The catalog case used all **116 repository-pinned archives**. It reused the
previously verified archive cache mounted read-only, checked every SHA-256
before static inspection and independently rehashed every archive afterward.
Static inspection had zero errors. No fresh live store metadata was read.
Games Prefix Manager remains store 130 / 1.0.1; the separate GitHub v1.0.2
release asset is outside this catalog result.

- **69 archives installed and were removed**, including exact managed
  version/digest receipts, frontend-byte checks and inventory readbacks.
- **47 were refused** by existing root, compatibility, architecture or
  archive rules without a managed plugin remaining installed.

Every ID/digest/outcome matches the earlier 30 October and main6a results.
Frame Control's HTTP/SSH installation and removal paths execute in this
private project. Official plugin backends and Steam CEF are stubbed in the
catalog case. Passing transport does not establish official plugin behavior
or controls. No compatibility rating, catalog identity or install policy changed.

## Runner and cleanup

The external runner starts from `scripts/framey-audit-fake.py` and changes only
the launch setup: use the frozen source checkout, run full unittest discovery
instead of the catalog-only class, give both images unique project-owned tags
with matching Compose overrides, capture live Docker inputs and remove those
owned image tags after Compose cleanup. Production sources, test bodies and
assertions are unchanged. Both runner hashes are recorded in the JSON.

The unique project `framey-catalog-9362b3b147` mounted the source and archive
cache read-only with the normal container-only e2e guard enabled. After the
successful run, independent Docker queries found **zero owned containers,
volumes, networks or image tags** remaining. The shared simulator was not
selected or reset. Existing archive data was retained. No real Frame, active
Steam session or pre-existing user data was contacted or changed.

## Limits

This closes the optional catalog-cache gap for the tested main commit. It does
not prove live Steam CEF, official backend functionality, real Frame input,
wearer-visible UI or physical-controller usability. The separate keyboard
event-path tests and their hardware limits remain documented separately.

Exact current-main CI and every applicable PR/release gate still apply.
This evidence does not qualify a future release commit, tagged installers,
checksums, publisher dry run or locked real Frame smoke test, and publishes
no release.
