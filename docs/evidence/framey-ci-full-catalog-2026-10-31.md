# Run the pinned catalog in hosted e2e

Previously the hosted e2e job passed while skipping the full-catalog case because its archive cache was absent. This change prepares every exact pin from the checked-out catalog, verifies cache hits, mounts archives read-only and retains installer outcomes. Hosted e2e checks out the exact PR head. Missing bytes, wrong hashes, oversized downloads and a missing copied result fail instead of silently reducing coverage.

## Announcement

Prepared mandatory full-catalog transport coverage for CI. Local AMD64 verification passes all 53 e2e tests without skips, including all 116 pins: 69 install/remove and 47 expected policy/archive refusals. This does not execute official plugin backends or promote compatibility ratings. Hosted ARM64 CI is still required; nothing is released.

## Verification

- A completely empty cache verifies all 116 exact pins: 37 repository fixtures and 79 real CDN downloads. Every restored-cache hit also verifies SHA-256; all 116 pass. A separate real CDN miss verifies store ID 74 at its exact 0.1.0-1 pin. Temporary cold-cache files were owned and removed.
- Seven regression tests cover real HTTP download, hash/size refusal, removal of owned partial files, corrupt-cache preservation, fixture verification and CLI failure reports. Full server suite: 1,959 tests in 255.668 seconds, 16 platform/optional skips. No server-test skip is described as a pass.
- The actual updated `scripts/e2e.sh` passes 53 tests in 401.796 seconds with zero skips. All 116 installer records match exact catalog IDs/digests. Docker inspection confirms `/audit-cache` and `/repo` are read-only mounts. The script copies its result to the host before teardown.
- Output-without-cache configuration exits 2 before the build. Cache failures return nonzero and retain per-pin diagnostics. Actionlint v1.7.7 exits 0 without diagnostics; zsh syntax passes.
- A separate negative control deliberately selects one passing non-catalog e2e case. Because no catalog result exists, the actual harness exits 2 at the result-copy gate. Its failed-harness banner is the expected refusal, not a failed full suite. The negative-control project also cleans up; stable simulator identity/start time/restart count and original image tags independently match.
- Owned e2e containers, volumes, network and temporary compose file are gone. Original image tags are restored. The pre-existing Frame simulator remains the same healthy running container, with start time predating the test interval.
- The initial local collector exited 1 after the tests and cleanup succeeded: it compared the simulator's full Docker State, including rolling `Health.Log` timestamps. The original observation is retained. Independent readback verifies container identity/start time, image tags and owned-resource absence; the suite was not repeated. Existing socket ResourceWarnings remain in the raw e2e log; no warning-free runtime claim.

Tested on base `fda7bcd86237033949d72a967c4e8fd41c9d46cc` plus the source hashes in the [audit](framey-ci-full-catalog-2026-10-31.json). [Raw logs, cache verification, installer outcomes, original collector and recovery](framey-ci-full-catalog-2026-10-31-raw.json.gz), SHA-256 `7e597754e226bd1c8a274277ce5701f2ec2f4126dde40f52bcd6b3c6207f2278`. The workflow is linted locally, not executed by GitHub here.

## Limits

Hosted exact-head CI, native ARM64 e2e and final current-main/feedback/mergeability gates remain pending. Transport/policy success does not prove official backend behavior, browser controls, actual Steam CEF, managed Frame installation or wearer/controller usability. No headset or schedule touched. Release still requires all exact release-commit, tagged installer/checksum/publisher and locked real Frame gates.
