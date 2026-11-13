# TabMaster negative-fixture recovery — 2026-11-01

Source `31c3ad5fc8b1e84a27b3a5d88cae3b27d2c2fe7f`, based on main `9b2f3c2634a61767ebc52099f595229b2515d96f`.
Production plugin code, installer, archive pins and classifications are unchanged.

[PR #511 native AMD64 job](https://github.com/saphid/frame-control/actions/runs/41279591518/job/124768592831) on exact head
`9fbbe2445a8dd83eae1aeafe85c71efd8f9d2d3d` passed PlayTime and the positive TabMaster scopes,
then failed during TabMaster's intentionally unpatched unload negative. The
first controlled EOF forced-stop is expected. The fixture restarted that same
unpatched backend and required its next stop to be clean; it instead forced
another stop. This unsupported negative-fixture assumption can fail whenever
another RPC connection reaches EOF. A local exact-PR repeat passed all three
scopes: the hosted failure is retained and is not relabeled a passing job.

The fixture now retains the first strict forced-stop negative, restores the
exact originally installed backend and IPC helper after its owned process
identities are reaped, then restarts and requires settings readback and a clean
parent-only stop. The report binds both restored hashes and still marks the
negative as a compatibility failure. No retry, skip or weakened stop assertion
is used.

Published Decky 3.3.0 native AMD64, networkless/device-free, passes all three
focused TabMaster cases. Each has two stops and settings persistence: positive
and valid-backup-restore negative have zero forced stops; unload negative has
exactly one forced stop followed by one clean repaired stop. Every owned
identity is reaped, unrelated sibling survives and complete console hashes are
independently checked. All 27 runtime source inputs match this Git commit.
The three runtime inventory tests also pass. Raw earlier/head/fixed reports and
hosted failure logs are retained in the compressed companion packet.

Full hosted CI, ARM64 and current-main qualification remain required. This
adds no browser, real Frame, user-library or worn/controller proof and qualifies
no release. No hardware, schedule, security settings or PR #113 was touched.
