# Repeatable installer audit command, 28 October 2026

The independent installer check used for v0.4.53 was previously a local
one-off script. The new script at scripts/audit-release-assets.py makes that
check repeatable before future releases are published. It reads the release
by exact tag or the draft's exact version title, requires ten installers plus
SHA256SUMS, downloads each by asset ID, checks size and SHA-256 against GitHub
metadata, matches the downloaded checksum file byte for byte, and inspects
package formats and versions. On an x86_64 Linux host, its optional flag also
launches the tagged x86_64 AppImage under isolated Xvfb.

The command writes a JSON report only after all checks pass and refuses to
overwrite an existing report. It performs no headset operation and makes no
GitHub changes. It does not prove physical Mac or Windows installer launch.

## Verification

- Eight focused offline tests passed, including incomplete metadata, wrong
  Mac bundle version, wrong AppImage architecture, a bad downloaded checksum
  file, and refusal to overwrite a report. Three existing checksum-generator
  tests passed.
- After v0.4.53 publication, the new command audited its public release with
  the tag v0.4.53, report path /tmp/frame-v0453-reusable-audit.json, and the
  --launch-x86-appimage option. It exited successfully after independently
  downloading all ten installers. Their names, sizes, hashes and package
  checks matched the [prepublication asset audit](v0453-assets-2026-10-28.json),
  and the downloaded SHA256SUMS had the same SHA-256:
  813441ac5c121e2c9effd274576aa6db1ff01187f811463a1014f86e0172608c.
  The x86_64 AppImage's bundled server returned HTTP 200 with FrameControl/1
  and stopped after app exit. The local JSON report had SHA-256
  ad8d7feaf6c0398b216f43c00206dd01d6efc714e3b341048bece96c0e5be376.

This postpublication repeat verifies the new command; it does not replace
the prepublication v0.4.53 release gates recorded in
[release verification](v0453-release-2026-10-28.md).
