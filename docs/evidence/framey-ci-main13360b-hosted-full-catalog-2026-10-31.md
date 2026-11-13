# Integrated full-catalog CI: exact-head hosted ARM64 proof

## Announcement

Full-catalog PR #532 at exact `e7f35e3352acb222051e3adf9d53fb427c266acf` passes hosted ARM64 e2e with **53 tests and zero skips**. All 116 restored cache entries are hash-verified against the integrated current-main catalog. The suite retains 69 install/remove and 47 expected refusal outcomes. Every outcome and refusal reason matches the complete local integration result. No backend functionality, Frame/VR usability or release claim follows.

## Verification

[Hosted e2e job](https://github.com/saphid/frame-control/actions/runs/41235942300/job/124639631299) runs 53 tests in 348.300 seconds. Logs verify exact checkout and the native ARM64/Holo base, actual cache verification, the full catalog case and actual result copying. There are no e2e skips. Current catalog manifest SHA-256: `e5c3309860e32e190c3810f73eec01d622001c69bbb0a7f0e10be7b2742f2b07`. Cache sources: 116 verified hits; cold-cache fixture/CDN download proof belongs to the prior unchanged-helper qualification.

Artifact `13055602207` in [run 41235942300](https://github.com/saphid/frame-control/actions/runs/41235942300) binds this exact head. Downloaded ZIP SHA-256 `4063679cd2b05388e486cff9450891d9816a15f2925f00a00f7ac3f03f2f95d0` matches GitHub's published digest. Both member sizes/hashes verify. Every ID, version and digest matches exact source; all 116 result records and refusal reasons match the local combined-source run. The 13 source fingerprints match both the published head and tested local source `503a7bec`.

[Audit](framey-ci-main13360b-hosted-full-catalog-2026-10-31.json), [raw cache/outcomes/metadata/logs/verifiers](framey-ci-main13360b-hosted-full-catalog-2026-10-31-raw.json.gz), SHA-256 `a0fb2c622efabaaf34ec18117afe5a33540e3f6af69409f86efcf8d46daffe6d`. Full downloaded artifact is retained in the linked run and local `build-watch/pr532-artifacts381`.

## Limits

The exact source implements read-only mounts and the teardown trap; the job succeeds and copies the result. No independent hosted post-job Docker-inspection packet was retained, so hosted resource absence is not independently claimed. Existing socket ResourceWarnings remain. Official backends do not execute in this transport audit; compatibility ratings do not change. All other exact-head checks/runs, completed current-main CI, feedback/mergeability and release gates require separate final review. No hardware or schedule touched. Actual Steam CEF, managed Frame and wearer/controller use remain unverified.
