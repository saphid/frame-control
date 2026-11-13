# Published v0.4.56 installer byte audit, 2026-10-30

A fresh read-only download audit of release 428483372 verified all ten
published installer sizes and SHA-256 values against GitHub metadata,
SHA256SUMS and update.json. Package inspections passed: all ZIP CRCs,
both Mac bundle versions, both DMG trailers, the Windows PE header, both
AppImage architectures and both DEB versions/architectures. Intel Mac DMG
and ZIP are included. The [report](v0456-installer-reaudit-2026-10-30.json)
binds the downloaded results to the unchanged published asset list.

The tag still resolves to 10af106f2dccfe2bd411dc1fc836c8e285d357f9. Its 15
current check results are successful, including e2e, both native Decky jobs
and all four tagged installer build jobs. This is a published-release
continuity check, not a new release or a new publication approval. Installer
runtime launches and physical Frame smoke were not repeated. No security
setting, release, tag, headset or user session was changed. The auditor
removed its own downloaded scratch files; only JSON/log proofs remain.
