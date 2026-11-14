# Terminal refresh after sample browser qualification, 14 November 2026

The branch normally includes accepted main `5adf2271`. The author documentation
and shared HTTP tests overlapped with #483/#705, requiring this fresh integration.
The complete product UI tree and six Terminal runner/probe files retain their
exact preceding-head bytes. The record includes their tree IDs and hashes.

The initial focused run caught two errors: new Syncthing diagnostics assumed
`frame_steam` re-exported `urllib`, while this PR's smaller status client no
longer imports it. The opt-in actual browser run exposed the same dependency
in its target metadata observer. Both fixtures now import their own stdlib
HTTP dependency. Existing failure-preservation and bounded diagnostic tests
pass without restoring or changing the production client.

All 134 focused tests and two actual Chromium startup tests pass. The latter
initialize the full pinned frontend/Framey runtime and exercise normal,
seven-second delayed-parent and 2 MiB-child delivery. The original focused
and actual browser failures remain in the compressed report.

The preceding local production HTTP replay and audited hosted AMD64/ARM64
replays remain prior-integration evidence in the mainc764 record. This refresh
does not claim a new local HTTP VM replay. Fresh exact-head hosted native,
browser/HTTP and full CI remain required. The preceding head still had six
checks running at the retained checkpoint and is not claimed fully qualified.

Official Terminal installation, real Steam/Frame, physical input, worn
visibility, scrolling and VR keyboard remain unverified. Historical ARM64
timeout/shutdown causes remain unproven; horizontal overflow remains visible.
