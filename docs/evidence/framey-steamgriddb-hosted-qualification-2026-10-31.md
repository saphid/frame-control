# Exact-head SteamGridDB hosted qualification

PR [#523](https://github.com/saphid/frame-control/pull/523), exact head `e0613730c893ebf4fbc0b9708e73d7711e010dff`, completes 18 successful checks. Main `fda7bcd86237033949d72a967c4e8fd41c9d46cc` still has running/queued checks at review; no merge or release is qualified by this record.

## Announcement

Qualified the scoped SteamGridDB child-IPC shutdown repair on published Decky 3.3.0 AMD64 and ARM64. Private artwork/settings survive two repaired stops and restart without forced plugin kills or recorded owned survivors. SteamGridDB remains **broken** because the required Steam-only LibraryContextMenu frontend is unavailable.

## Evidence

- Eight downloaded artifacts independently bind 1,363 source hashes across 149 exact-head files. Published loader digests verify. Both native architectures retain 46 cases, including eight expected regression controls; their expected failures do not establish globally clean runtime.
- Repaired/original SteamGridDB completes 14/12 RPCs on each architecture. Repaired stop times are 0.185/0.185 seconds AMD64 and 0.214/0.195 seconds ARM64. Original-source controls still force-stop after 5.226/5.227 seconds. All five settings/artwork/VDF snapshots independently decode, hash and match expected contents before/after stops. The unrelated sibling survives.
- Independent exact-archive installation preserves every other published archive member; the backend retains all original bytes beneath only the EOF prefix. The shared IPC helper matches the exact qualified source.
- Simple Timer retains 31/10/18 RPCs, four repaired clean stops, hashed persistent settings and original/previous-managed negative controls on both architectures.
- Ownership, native sync and actual user-service fixtures verify owned cleanup. All four signed-package modes pass signatures, lifecycle, preserving uninstall and owned cleanup. Browser result packets independently decode with matching lengths/checksums. The production-parent HTTP mode retains the production iframe and sandbox, 64 successful parent requests and no recorded parent errors. It uses synthetic CEF; actual Steam CEF and managed Frame remain unverified.
- Hosted fake-Frame e2e ran 53 tests in 234.938 seconds with **one optional full-catalog-cache skip**. No supplemental full-catalog test ran in this qualification. Earlier local server/website/installer results in #523 are historical and were not repeated.
- Independent whole-checker/source/AST audit preserves main's other runtime bodies, top-level controls, native cases, installer/payload/e2e branches, catalog entries/policies and Timer helpers. Main's new packer paths and this PR's changed paths are disjoint. No hosted combined-tree proof is claimed.
- Reviews, review comments, issue comments and unresolved threads were empty at review. Fresh exact-main/head/checks/feedback/mergeability/behind-or-overlap gates remain mandatory.

[Native](https://github.com/saphid/frame-control/actions/runs/41223679784), [ownership](https://github.com/saphid/frame-control/actions/runs/41223679717), [package modes](https://github.com/saphid/frame-control/actions/runs/41223679748), [CI/e2e](https://github.com/saphid/frame-control/actions/runs/41223679593).

[Audit](framey-steamgriddb-hosted-qualification-2026-10-31.json) and [raw reports, logs and verifiers](framey-steamgriddb-hosted-qualification-2026-10-31-raw.json.gz), SHA-256 `08ef6f1e3fc3cfcb6613f25787a2b40f545e08ff307d0012a19c9b443680e98d`. Complete package reports, packets and images remain in linked artifacts and local state, with archive/member hashes retained here.

## Limits

No globally clean runtime, LibraryContextMenu, external artwork service, browser, actual Steam CEF, managed Frame, wearer/controller, tagged installer or release proof. No headset, schedule or pre-existing user data touched. Release remains held for all exact release-commit gates and locked real Frame smoke.
