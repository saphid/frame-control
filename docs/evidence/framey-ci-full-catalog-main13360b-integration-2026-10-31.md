# Full-catalog CI integration with current main

## Announcement

Normally integrated main `13360b13017bbb1a16c5ee6472bb15b5ea996586` into #532 without conflicts. The branch preserves main's product source and the existing workflow/cache implementation. The actual updated e2e script passes all 53 tests with zero skips on the combined AMD64 source, including all 116 exact catalog pins: 69 install/remove and 47 expected refusals. Nothing is released.

## Verification

- Tested merge source `503a7bec89eb8cca1afeb69efcab9bfaed8ea058`, with parents `57eb0bc1c46247662beb053d4649819330281ac6` and `13360b13017bbb1a16c5ee6472bb15b5ea996586`. All eight original PR files are unchanged; all 20 qualified native-runtime source inputs equal main. Native AMD64/ARM64 results are inherited by identical inputs, not claimed as a new execution.
- Full server suite: 1,959 tests in 255.109 seconds, 15 platform/optional skips. All seven cache regression tests and 18 website tests pass.
- Actual `scripts/e2e.sh`: 53 tests in 397.858 seconds, zero skips. Cache helper verifies all 116 restored ZIP hashes against current catalog `e5c3309860e32e190c3810f73eec01d622001c69bbb0a7f0e10be7b2742f2b07`. Every installer outcome and refusal reason equals the previous complete integration result.
- Independent Docker inspection verifies read-only `/repo` and `/audit-cache` mounts. The actual script copies its result before teardown. Owned containers/volumes/network/temp files are absent, original image tags restored, and the pre-existing healthy simulator retains its ID/start time/restart count. Cleanup deletes only images created by this run.
- Earlier cold-cache and missing-result controls remain bound to the unchanged helper/harness in [the original record](framey-ci-full-catalog-2026-10-31.md). Original head `57eb0bc1` passed hosted ARM64 53/0 and 13 checks; that is historical proof, not new-head CI. [Hosted supplement](https://github.com/saphid/frame-control/blob/4a2f7a4cb89d941e7ad4ebc7ad3528fecdc62d62/docs/evidence/framey-ci-hosted-full-catalog-2026-10-31.md) is in #531.

[Audit](framey-ci-full-catalog-main13360b-integration-2026-10-31.json) and [raw logs/source bindings/outcomes/verifiers](framey-ci-full-catalog-main13360b-integration-2026-10-31-raw.json.gz), SHA-256 `cd740dfd0e08c665b73e0a9b4623b68929f541a4c51fe9257f9be7b222128d01`. Existing socket ResourceWarnings remain. No warning-free or generic clean-runtime claim.

## Limits

Combined-head hosted CI/ARM64 and final current-main/feedback/mergeability gates remain pending. Transport tests do not execute official backends or establish actual Steam CEF/Frame/wearer/controller usability. No hardware or schedule touched. Release remains held for every exact release-commit, tagged installer/checksum/publisher and locked real-Frame gate.
