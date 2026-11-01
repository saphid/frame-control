# Hosted ARM64 full-catalog e2e qualification

Exact [#532](https://github.com/saphid/frame-control/pull/532) source `57eb0bc1c46247662beb053d4649819330281ac6` ran on hosted `ubuntu-24.04-arm`. This supplements the earlier local-only record; it does not turn historical skips on other heads into passes.

## Announcement

Verified the full pinned catalog in hosted ARM64 CI: **53 e2e tests, zero skips**, including all 116 exact pins. The retained outcomes are 69 install/remove and 47 expected policy/archive refusals. Official plugin backends do not execute in this fake-Frame test. Compatibility ratings and release status stay unchanged.

## Evidence

- [Exact-head job](https://github.com/saphid/frame-control/actions/runs/41231625387/job/124626860156) completes successfully; checkout logs and run/job/artifact metadata all bind `57eb0bc1c46247662beb053d4649819330281ac6`. The ARM64 Holo base appears in build logs.
- Cold cache verifies 37 repository fixtures and 79 CDN archives. Every ID, version and digest matches the exact-head manifest SHA-256 `c9745e9563639b37d582bd62d5a8c447a958b22e73174bf07898a115c1d6cebb`. Each retained outcome independently matches the prior complete local result, including its refusal reason.
- The actual catalog test is `ok`; the complete suite ran 53 tests in 330.513 seconds and reports `OK`, with no skips. The updated harness copies its result before teardown. The 400-second total includes builds.
- Artifact `13053544643` (`e2e-catalog`) ZIP SHA-256 `e1933c995951bd7d19e3eb781d2b9f831ae5278b32b03d7f1d5e758f94f22700` matches GitHub's published digest. Its cache/result member hashes verify. [Workflow artifacts](https://github.com/saphid/frame-control/actions/runs/41231625387).
- All 13 locally qualified source fingerprints are identical at the hosted checkout, including workflow/cache/harness/catalog/installer files. Read-only cache binding and teardown trap are verified in exact source. The hosted job passes, but no independent post-job Docker-inspection packet was retained; hosted resource absence is not separately asserted.
- Existing unclosed-socket ResourceWarnings remain in the log. No warning-free runtime claim. Reviews, comments and unresolved threads were empty at qualification.

[Audit](framey-ci-hosted-full-catalog-2026-10-31.json), [raw metadata, cache/outcomes, log and verifier](framey-ci-hosted-full-catalog-2026-10-31-raw.json.gz), raw SHA-256 `5746e776bd2608e9fe3f0287d3ce2153b000104c742695a4aa1fb2d6f5b8bca6`.

## Limits

This record qualifies the completed e2e job, not every check or merge gate. Exact-current-main CI, remaining PR checks, fresh feedback, behind/overlap and mergeability still gate merging. No official backend/UI, Steam CEF, managed real Frame, wearer/controller, tagged installer or release proof. Hardware and schedules were untouched. Release still requires all exact release-commit gates and locked real Frame smoke.
