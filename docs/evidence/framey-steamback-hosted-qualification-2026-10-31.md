# Exact-head Steamback hosted qualification

PR [#527](https://github.com/saphid/frame-control/pull/527), exact head `c50a2337218bdefc83851b31eff07085c43b6e1e`, has 18 successful hosted checks. This record independently audits the results; it does not authorize a merge or release. Current main `fda7bcd86237033949d72a967c4e8fd41c9d46cc` still had running/queued checks at review.

## Announcement

Qualified the scoped Steamback shutdown repair on published Decky 3.3.0 AMD64 and ARM64. Private backup/restore/undo and restart preserve the recorded save bytes, the original unload hook completes, and no forced kills or owned survivors are recorded for repaired stops. Compatibility remains **partial**; real Steam saves, automatic game triggers, browser, Steam CEF and real Frame usability remain unverified.

## Evidence

- Eight downloaded artifacts bind 1,363 report hashes to 149 files at the exact head. Both published loader digests verify. Each architecture retains 46 native cases and eight expected regression controls; expected failures are not clean-runtime passes.
- Steamback repaired/original: 11/9 RPCs on each architecture. Repaired stop times: AMD64 0.185/0.214 seconds; ARM64 0.214/0.214 seconds. Original-source controls still force-stop after 5.227/5.229 seconds. Base64 save, backup and undo snapshots independently decode and hash; before/after contents match. The unrelated sibling remains alive.
- Independent installation preserves every published archive member beneath the exact EOF prefix and shared helper; removal cleans the owned fixture. Original save-engine source is unchanged.
- Simple Timer controls retain 31/10/18 RPCs, four repaired clean stops, hashed persistent settings, original-state failures and previous-managed forced-stop controls on both architectures.
- Ownership reports verify owned watchdog cleanup, two-way sync and the actual user-service fixture. All four signed-package modes verify signatures, lifecycle, preserving uninstall and owned cleanup. Complete browser result packets decode with matching length/hash. The production-parent mode retains the production iframe and renderer sandbox, 65 successful parent requests and no recorded parent errors. It uses synthetic CEF; no actual Steam CEF or managed Frame proof follows.
- Hosted fake-Frame e2e ran 53 tests in 241.493 seconds with **one optional full-catalog-cache skip**. This turn did not run a supplemental full-catalog test. Earlier local server/website/installer records in #527 are historical, not rerun here.
- Current-main source/AST comparison preserves every other runtime body, installer branch, native case, catalog policy, shared IPC helper and Timer control. Main's new packer paths and this PR's changed paths are disjoint. Main is not integrated into this PR, and no hosted combined-tree proof is claimed.
- Reviews, review comments, issue comments and unresolved threads were empty at review. Recheck exact heads, current main, required checks, feedback, behind/overlap status and mergeability before merging.

[Native](https://github.com/saphid/frame-control/actions/runs/41224634996), [ownership](https://github.com/saphid/frame-control/actions/runs/41224634877), [package modes](https://github.com/saphid/frame-control/actions/runs/41224634868), [CI/e2e](https://github.com/saphid/frame-control/actions/runs/41224635020).

[Audit](framey-steamback-hosted-qualification-2026-10-31.json) and [raw reports, logs and verifiers](framey-steamback-hosted-qualification-2026-10-31-raw.json.gz). Raw SHA-256: `cd77d5091b09ef960e94fcf22b2775d621ef6b3744c8a53679e833cbd5e0596b`. Complete package reports/packets/images remain in linked artifacts and local state, with their archive/member hashes retained here.

## Limits

Generic runtime console qualification remains false; published warnings and negative histories remain. No global clean-runtime, actual user saves, automatic triggers, native desktop UI, real Steam CEF, managed Frame, wearer/controller, tagged installer or release proof. No headset, schedule or pre-existing user data was touched. Release remains held for every exact release-commit gate and locked real Frame smoke.
