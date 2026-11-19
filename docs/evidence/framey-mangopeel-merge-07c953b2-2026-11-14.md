# MangoPeel accepted merge, 14 November 2026

PR #509 merged as `07c953b2` after all 25 exact-head hosted checks passed.
The current-main integration passes all 160 focused tests and the native
AMD64 positive and negative MangoPeel replay. GitHub's merge tree and both
parents exactly match the tested integration.

Both architectures' full-runtime and Terminal-candidate artifact sizes,
ZIP digests, pinned loaders, source bindings and console digests independently
verify. The stricter MangoPeel audit checks 61 source hashes per full report,
controlled child IPC EOF, a successful later RPC, parent-only signal, recorded
descendant identities, no remaining recorded descendants, preserved unrelated
process/profile and cleanup. Positive stop times are 0.214s locally, 0.186s
hosted AMD64 and 0.185s hosted ARM64, with no forced plugin kills or errors.

The prior watch-only negative has no child IPC helper and reproduces exactly
one forced plugin kill after 5.223s locally, 5.194s hosted AMD64 and 5.213s
hosted ARM64. It explicitly remains an unqualified compatibility control.
The earlier failed control metadata and original refresh evidence remain intact.

These are isolated private-profile/watch checks. Actual MangoHud rendering,
Steam/Frame behavior, physical controller input and worn VR remain unverified.
