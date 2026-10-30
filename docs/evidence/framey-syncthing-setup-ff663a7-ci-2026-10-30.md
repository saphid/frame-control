# Syncthing setup CI at ff663a7, 30 October 2026

[PR #477](https://github.com/saphid/frame-control/pull/477), exact head
`ff663a76d22b151abd1ecac1acbd9f62e862fc6d`, passed its browser workflow.
Independent audit matched the GitHub artifact digest, all exact-head and
case-level source fingerprints, the exact official archive/candidate frontend,
expected calls/settings, original negative failure, all five candidate cases
and browser cleanup. All six retained captures were inspected.

The archive is [artifact 12977350738](https://github.com/saphid/frame-control/actions/runs/41055355147/artifacts/12977350738),
SHA-256 `87eb21f7cd1b49948e1c18c691d7f8b6c47460edc23a54be3354b8f8a585fa5c`.

- [original](framey-syncthing-setup-ff663a7-original-2026-10-30.png)
- [fresh](framey-syncthing-setup-ff663a7-fresh-2026-10-30.png)
- [migrating](framey-syncthing-setup-ff663a7-migrating-2026-10-30.png)
- [configured](framey-syncthing-setup-ff663a7-configured-2026-10-30.png)
- [finish-navigation](framey-syncthing-setup-ff663a7-finish-navigation-2026-10-30.png)
- [manual-port](framey-syncthing-setup-ff663a7-manual-port-2026-10-30.png)

The original remains on Loading. Fresh setup reaches Finish; migrated settings
reach the installation-method entry. Configured, finish-navigation and manual
fallback cases retain the expected synthetic missing-unit error. The manual
fallback capture is its final error view; method/settings evidence establishes
the entered fixture port, not a screenshot of the input itself.

All backend responses in this browser workflow are synthetic. This is not an
actual service-control, managed-install, SteamVR or controller pass. Fresh
native ownership and signed-package checks remain required. The earlier head's
AMD64 sync failure is retained in its separate evidence; it is not cleared by
this browser result. Syncthing stays blocked from managed installation. No real
Frame was contacted and no release was attempted.

Both fresh ownership-candidate artifacts from run `41055355149` were
independently audited against exact head `ff663a7`: AMD64 artifact
`12977455387` and ARM64 artifact `12977685204`. Their digests, all source
fingerprints, 11 Rust tests, actual Decky discovery/RPC, two-way Syncthing
2.1.7 sync, 17 actual user-service results and 18 ownership refusals passed.
This is the separate ownership runtime, not signed Syncthing 1.27.3 Flatpak
proof. Fresh signed-package jobs were still pending at this audit.
