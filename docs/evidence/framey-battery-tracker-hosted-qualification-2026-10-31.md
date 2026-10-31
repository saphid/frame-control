# Exact-head Battery Tracker qualification

PR [#519](https://github.com/saphid/frame-control/pull/519), exact head `0c921258d1cd5367d2683d1d1eaafeaac90cd652`, completes 18 successful hosted checks. Main `fda7bcd86237033949d72a967c4e8fd41c9d46cc` still has running checks at review; no merge or release is qualified by this record.

## Announcement

Qualified Battery Tracker 0.2.0/store 67's pending-sample unload repair on Decky 3.3.0 AMD64 and ARM64. The repaired recorder flushes pending samples on two framework stops and preserves them across restart; the previous-managed control retains forced termination and sample loss. Compatibility stays **partial**. Real battery, long-term recording, charts, managed Frame and wearer/controller behavior remain unverified.

## Evidence

- Eight downloaded artifacts bind 1,363 source hashes across 149 exact-head files. All eight ZIPs match GitHub-published digests and exact-head metadata. Both published Decky 3.3.0 loader digests verify; each architecture retains 46 native cases. Expected negative controls remain failures, not compatibility passes.
- Repaired/previous-managed cases retain 38/36 RPC observations per architecture; polling counts are observations rather than a fixed API contract. Repaired stops are AMD64 0.214/0.175 seconds and ARM64 0.185/0.215 seconds, with zero forced plugin kills, zero adopted-child exit failures and no recorded owned survivors. The unrelated sibling survives.
- Repaired private SQLite rows grow from zero to two on the first flush, survive restart and grow to three on the second. Both per-architecture final database snapshots independently decode from base64, verify SHA-256 and `PRAGMA integrity_check`, and match exact ordered SQL rows. Fixed private battery/app fixtures exercise recording; these are not real sensor measurements.
- Previous-managed controls force-stop at 5.184/5.229 seconds and retain zero rows, reproducing loss of pending samples. Their SQLite snapshots remain structurally valid: database integrity alone does not prove sample persistence. Generic runtime-console clean-shutdown verdicts stay false.
- Independent owned-fixture installation/removal verifies the receipt, exact EOF prefix/helper, preserved prior user/battery backend and five other original archive files. The existing scoped root-request removal is preserved and its manifest otherwise matches the published archive. Archive SHA-256: `91c388d3c1b52079314045b79671ad55c767510658b6193f6936ed6cad383b94`.
- Simple Timer retains 31/10/18 RPCs, four repaired clean stops, hashed persistent settings and original/previous-managed failures on both architectures. Whole-checker/runner/installer AST comparison preserves unrelated main probes/controls, native cases, installer/e2e branches and catalog policies. The prior Battery Tracker lifecycle helper/body/negative are unchanged. Main packer paths are disjoint; this is not hosted combined-tree proof.
- Native ownership, two-way sync, actual user service and all four signed-package modes verify preserving lifecycle/removal and owned cleanup. Browser packets decode with matching lengths/hashes; production-parent HTTP retains 64 successful requests, unchanged production iframe/sandbox and no recorded parent errors. Those browser jobs cover **package/Syncthing controls, not Battery Tracker charts**, and use synthetic CEF.
- Hosted fake-Frame e2e runs 53 tests in 238.620 seconds with **one optional full-catalog-cache skip**. #532's later complete catalog proof has a different source head and does not erase this skip. Earlier local server/website/installer results remain historical; no full local suite was rerun in this artifact qualification. Existing historical evidence in the original worktree is untouched; no stale outer gzip hash is adopted by this record.
- Reviews, review comments, issue comments and unresolved threads were empty at review. Fresh exact-main/head/checks/feedback/mergeability/behind-or-overlap gates remain required.

[Native](https://github.com/saphid/frame-control/actions/runs/41225711077), [ownership](https://github.com/saphid/frame-control/actions/runs/41225711116), [package modes](https://github.com/saphid/frame-control/actions/runs/41225711071), [CI/e2e](https://github.com/saphid/frame-control/actions/runs/41225710946).

[Audit](framey-battery-tracker-hosted-qualification-2026-10-31.json), [raw native reports/SQLite snapshots/logs/verifiers](framey-battery-tracker-hosted-qualification-2026-10-31-raw.json.gz), raw SHA-256 `276529e79d25501e60b9e48b2689e122b333335ceb0e29aa9fc83bd83258b0de`. Complete package reports/packets/images remain linked hosted artifacts and local state, with original member/ZIP hashes retained here.

## Limits

No globally clean runtime, real battery, long-term recording, chart/browser refresh, actual Steam CEF, managed Frame, wearer/controller, tagged installer or release proof. No headset, schedule or pre-existing user data touched. Release remains held for every exact release-commit gate and locked Frame smoke.
