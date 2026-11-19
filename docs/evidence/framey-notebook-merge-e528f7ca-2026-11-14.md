# Notebook merge qualification, 14 November 2026

PR #497 merged as `e528f7ca94b529e7356807b5d66b62731becdf6c` after all
21 hosted checks passed at head `ee5c3b09615fd99e57c853b82459bf335decacd5`.
The independent audit verified both native AMD64/ARM64 artifact ZIP digests,
all 55 input hashes, all 41 primary cases, 35 negative controls, and all 76
console digests per architecture. Primary cases had no forced plugin kill or
shutdown-error marker. Artifact IDs and digests are retained in the JSON.

The head's cached GitHub test-merge ref still used main `072e7284`. A local
merge with current main `dba4e351` retained the inventory receipt-cap change
byte for byte and was qualified separately. All 55 runtime inputs were
byte-identical to the audited green head on both architectures. A new native
AMD64 Notebook run on that combined tree passed 33 legacy RPCs, per-app file
readbacks, selection and stroke persistence across restart, empty pages,
selected-delete isolation, and two zero-exit parent-only loader stops. The
console records both completed shutdowns with no forced kill or shutdown error.
The generic cleanup recorder's clean-shutdown flag remains diagnostic false
after the specialized probe has already stopped its loaders; it is not used
as a blanket process audit. All 28 focused tests passed without skips.

The coordinator checked the exact PR head, current main and review state,
then merged normally with an exact-head guard. The returned GitHub merge tree
`9a4bca4295db44182ee9aef661d03a1226184e77` and both parents exactly matched
the locally tested integration. The merged tree includes the newer receipt cap.
This avoided changing the already qualified PR source merely to refresh
GitHub's cached test merge.

The compressed raw report and JSON summary retain source hashes and console
proof. Compatibility ratings and the installed Notebook backend are unchanged.
Production HTTP integration, real Steam game transitions, artwork, Frame
rendering, worn visibility and physical controller input remain unverified.
This qualifies the PR merge, not a later version's release or hardware smoke.
