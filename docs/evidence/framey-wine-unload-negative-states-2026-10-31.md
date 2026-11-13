# Wine Cellar prior-source unload evidence

The strict original-source negative required a zombie helper. A private integration of main `51841728`, #514 `e6899841` and #516 `ab18a503` instead retained the same owned helper as a sleeping orphan (state `S`, parent 1), plus one forced plugin kill and loader exit zero. The helper PID/start identity survived. The old assertion rejected this run. The complete available failed output and observation remain evidence of a failed run, not a passing integration.

Unchanged standalone #516 and private-integration replays subsequently produced the previously expected zombie and passed. This does not establish that #514 caused the difference, or establish its scheduling cause. Retrying is not the fix: the captured sleeping-orphan observation is replayed deterministically through the corrected gate.

The negative now requires parent-only signalling, exactly one forced plugin kill, a zero-exit loader with its shutdown record, and evidence of the original helper becoming a zombie or remaining as a live orphan. Samples must match its original start identity. The report records each state separately. A live orphan additionally requires the exact helper to remain and a sampled parent of 1. Neither state is clean qualification. The positive gate still requires the helper to be reaped, no forced plugin kill and the existing successful unload records.

Validation at frozen source `f6bce259848b23c2664912421f66e2420ac7daca`:

- Seven host tests replay the actual orphan, zombie and clean-positive observations. They also reject reused identities, missing/multiple forced kills, missing shutdown output, failed loaders, group signalling and a supposedly orphaned helper still owned by its original parent.
- Published native Decky 3.3.0 AMD64 on current main: twelve runtime source fingerprints, seven positive and four negative read-only RPCs, two clean parent-only positive stops (0.201/0.251 seconds) and the original one-forced-kill zombie negative.
- Private integration with #514/#516 and the correction: fifteen source fingerprints, the same eleven RPCs, two positive stops (0.201/0.253 seconds), the original forced-kill zombie negative, and complete available console hashes after cleanup. The general console report intentionally keeps `cleanShutdownVerified: false`.
- The initial integration's separate Shotty run passed its positive and prior-source controls before the Wine assertion failed. It does not qualify the combined full matrix.

The fresh corrected native runs observed zombies; live-orphan acceptance is demonstrated by replaying the actual captured failure, not by claiming a new native orphan observation. Product, published archive/helper, IPC implementation and all catalog bytes are unchanged. This is targeted local AMD64 evidence. Full hosted CI/e2e, native AMD64/ARM64, ownership, every package mode, exact current main and final merge review remain required. No Frame, Steam CEF, wearer/controller, compatibility promotion or release was tested or published.

The audit JSON binds the raw gzip bundle, failed log and unit log. The raw bundle preserves reports, full available native consoles, process samples and private-integration source/tree provenance. Synthetic integration commits are local test preparation, not PR heads. Reconstruct the trees from the named main/#514/#516 heads and correction if reviewing the integration; do not treat their hashes as hosted CI proof.

## Refresh onto Shotty main

Main `1c1e4f588735dc3119f67f90ca8c33d3a90563cd` was merged normally at source `50cc009eefa9fcbcc04941f1c91d4c2cf4af9e60`. The Wine correction and captured-observation diff is identical to the previous PR head. Product/catalog bytes and Shotty runtime sources match current main. All 84 focused host tests pass: seven captured-observation replays, 17 compatibility checks and 60 store checks. Generated documentation and shim coverage pass, retaining all 33 declared native cases including Shotty and Wine.

The previous head `fd01d7a4604a300a81d071879a1117ff07d95739` passed all 13 hosted checks, exact merge-tree core/e2e audits and published native AMD64/ARM64 audits (39 probes, 33 archive pins and 12 source fingerprints each) against main `51841728`. Those results are historical. The refresh has no new local native run; full exact-head hosted qualification and current-main CI remain pending. The applicable workflow set must be checked from the actual changes; unrelated package/ownership workflows may not trigger for this test-only change. No real Frame or release qualification is claimed.

The [refresh audit](framey-wine-unload-main1c1e4f5-refresh-2026-10-31.json) binds the tested source tree and [focused log](framey-wine-unload-main1c1e4f5-refresh-2026-10-31.log). Later evidence-only commits do not change the tested runtime sources.
