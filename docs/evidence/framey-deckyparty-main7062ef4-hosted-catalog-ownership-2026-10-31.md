# DeckyParty integration: hosted catalog and ownership

## Announcement

Exact current-main DeckyParty head `9bec4ddc5242a912415be602165f3e93638ffe4f` qualifies hosted ARM64 fake-Frame e2e with 53 tests and zero skips, all 116 pinned catalog records, and native ownership/runtime/two-way-sync/user-service fixtures on AMD64 and ARM64. Separate native plugin evidence binds this same head; all four package modes and final merge/release gates remain separate. Compatibility claims are unchanged.

## Evidence

- [Exact-head e2e job](https://github.com/saphid/frame-control/actions/runs/41238231060/job/124646417921): 53 tests in 343.137 seconds, zero skips. All 116 restored cache hits independently match catalog ID/version/digest and manifest SHA. 69 install/remove and 47 refusal records, including reasons, exactly match the full local result. Artifact `13056468926` ZIP and both member hashes verify. Logs show the exact head checkout and actual catalog-result copy. This transport/installer suite does not execute official plugin backends.
- [Ownership run 41238231101](https://github.com/saphid/frame-control/actions/runs/41238231101): both ZIPs and every member hash verify; 42 source-hash bindings across 14 files match the exact head, with both pinned published Decky 3.3.0 loader digests checked. Both architectures retain loader-exit watchdog cleanup, forced-plugin-termination release, actual two-way sync, owned-process reaping and actual private user-service lifecycle, with host bus unexposed and the installer disabled. These are isolated Syncthing candidate fixture results, not real Frame or official plugin UI proof.

The source's read-only cache mount and failure-propagating cleanup trap verify, and the hosted job is successful. There is **no independent post-job Docker-absence packet**; no stronger cleanup assertion is made. Socket ResourceWarnings remain in the raw log. Generic globally clean runtime, actual Steam CEF, managed Frame, wearer-visible/controller and release behavior remain unverified. No headset, schedules or pre-existing user data touched.

This packet was prepared while source checks were running. [Summary](framey-deckyparty-main7062ef4-hosted-catalog-ownership-2026-10-31.json), [raw reports, job/log, metadata and verifiers](framey-deckyparty-main7062ef4-hosted-catalog-ownership-2026-10-31-raw.json.gz), SHA-256 `c90c9c5b597256e1fb7b95c5ff574473a73a18d7a6cba9f92a1f61f7e3469203`.
