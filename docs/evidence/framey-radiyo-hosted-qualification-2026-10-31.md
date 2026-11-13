# Exact-head RadiYo qualification

PR [#520](https://github.com/saphid/frame-control/pull/520), exact head `44ba8459e382ce2afbd5b7b6d9b0b89296b21264`, completes 18 successful hosted checks. Main `fda7bcd86237033949d72a967c4e8fd41c9d46cc` has 14 successful checks and a live ARM64 package job at review. The #525 TabMaster dependency/merge hold remains; this record does not qualify a merge or release.

## Announcement

Qualified RadiYo! 1.3/store 24's child-IPC EOF repair on published Decky 3.3.0 AMD64 and ARM64, retaining the prior verified-TLS repair. Private loopback HTTP/restart and bounded lifecycle checks pass. Existing copies need Update/reinstall; compatibility remains **partial**. External stations, trusted public HTTPS, audio, RadiYo UI, actual Steam CEF/Frame and wearer/controller behavior remain unverified.

## Evidence

- Eight ZIPs match GitHub-published digests and exact-head metadata. 1,363 source-hash bindings verify across 149 files. Both published Decky 3.3.0 loader digests match; 46 native cases each retain their discovery results and eight explicit regression cases. Expected failed controls remain failures, not compatibility passes.
- Repaired/previous-managed RadiYo retain 9/7 RPCs each. Both fetch and redirect paths reject self-signed HTTPS; loopback body/header/redirect readbacks persist across restart. Repaired parent-only stops are AMD64 0.185/0.185 and ARM64 0.214/0.214 seconds, zero forced plugin kills, selected stop errors or recorded owned descendants; adopted exits are zero and an unrelated sibling survives. Previous-managed negatives force-stop at 5.228/5.229 seconds.
- Independent owned-fixture installation/removal checks the exact receipt, EOF prefix and unchanged shared helper. Reconstructing the prior TLS backend directly from archive SHA-256 `647111578aa7a5ecd16af8d7fe6c068a6d7ea8737c6dce5ac2d52e84a549ec43` reproduces exact bytes under the prefix; every other published member is preserved. This is an isolated fixture, not a user's installation.
- Simple Timer retains 31/10/18 RPCs, hashed settings/event/restart state, four repaired clean stops and original/previous-managed negatives per architecture. Generic runtime-console clean-shutdown verdicts remain false; scoped lifecycle proof is not globally clean-plugin proof.
- Whole-checker/runner/installer AST audits retain current main's other 36 runtime bodies, 33 cases, 115 complete catalog rows, all 116 policies and e2e/compatibility/Timer assertions. Prior RadiYo probe/helper/negative/TLS behavior remains unchanged. All 20 native inputs match tested source `955ce6dba2497a2eeecc139672941c328c15e5df`; final head is evidence-only. Main's newer VM-packer paths are disjoint, not tested combined-tree evidence.
- Native ownership, two-way sync, actual user service and all four signed-package modes verify preserving lifecycle/removal and owned cleanup. Browser packets decode with matching length/SHA. The production-parent fixture records 64 successful requests, maximum 9.237 seconds, unchanged sandboxed iframe and no parent errors. **These browser jobs cover package/Syncthing controls, not RadiYo UI or audio**, and use synthetic CEF. Their screenshots were not visually re-audited here.
- Hosted fake-Frame e2e runs 53 tests in 238.394 seconds with **one optional full-catalog-cache skip**. #532's complete catalog result has another source head and does not erase this skip. Earlier local server/website/37-pin installer results remain historical; no full local suite was repeated for this hosted artifact qualification.
- Earlier TabMaster positive-case first stop remains a strict failure: forced kill at 5.225 seconds without its unload hook. Original report, console/hash and failed audit are retained here; RPC/backup-restore success does not waive that failure. #525 owns the repair; its separate positive evidence does not rewrite this historical result. #520 remains behind that dependency's qualification/merge gate.
- Reviews, review comments, issue comments and unresolved threads were empty at review. Fresh exact-main/head/checks/e2e/applicable native/package/feedback/mergeability/behind-or-overlap gates remain mandatory.

[Native](https://github.com/saphid/frame-control/actions/runs/41227746873), [CI/e2e](https://github.com/saphid/frame-control/actions/runs/41227746761). Artifact inventory retains authoritative run IDs for all eight downloads.

[Audit](framey-radiyo-hosted-qualification-2026-10-31.json), [raw native reports/retained TabMaster failure/logs/verifiers](framey-radiyo-hosted-qualification-2026-10-31-raw.json.gz), raw SHA-256 `6216cafcc47ea0a3f93b23fc6bda766611bb4802caebf8997d970767f0ebdeb9`. Complete package/ownership reports and browser packets/images remain hosted artifacts/local state, with original ZIP/member hashes retained here.

## Limits

No globally clean runtime, public radio stations, trusted public HTTPS, audio playback, RadiYo UI/browser refresh, actual Steam CEF, managed Frame, wearer/controller, tagged installer or release proof. Headset, schedules and pre-existing user data untouched. Release held for every exact release-commit gate and locked real Frame smoke.
