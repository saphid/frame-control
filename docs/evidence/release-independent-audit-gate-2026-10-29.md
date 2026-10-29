# Independent installer audit publication gate, 29 October 2026

The publisher previously checked exact-commit CI, tagged installer jobs,
SHA256SUMS and locked Frame smoke, while the independent installer download and
package audit remained a manual release step. This change makes the saved
`scripts/audit-release-assets.py` report a required input to both the publisher
dry run and publication.

The verifier binds the report to the current draft release ID and tag, its
SHA256SUMS digest, and all ten current installer names, sizes and SHA-256
digests. It requires recorded package-format checks and the isolated x86_64
AppImage launch. A missing report, stale digest, incomplete installer set,
missing launch, or unrelated draft asset stops before release mutation. A
prior `update.json` from an interrupted publisher attempt may be replaced only
after the other gates pass and its new bytes are read back.

Local fake-GitHub tests passed: 18 publisher cases, 13 independent asset-audit
cases, three checksum cases and six Frame-smoke result cases. Python compilation,
shell syntax and `git diff --check` passed. The tests include positive dry-run
and publication paths and negative stale or absent audit paths. No real release
was tagged or published, no installer was downloaded for this change, and the
Frame was not accessed. Hosted CI on the exact PR head is a separate gate.

The historical v0.4.53 audit report did not record the isolated AppImage
launch inside the report, although that launch was recorded separately in the
release evidence. The new gate applies to future draft publications; it does
not change the already published release or prove physical Mac, Windows or
worn-headset behavior.
