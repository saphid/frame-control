# Emuchievements 2.0.5 managed helper evidence

The official archive `tests/fixtures/framey-official/28.zip` has SHA-256
`98dcb443e81b9f9011cfe77c69eb659869c8e2df2df8b0a443df66cbfc2f5a89`.
Its x86 helper is replaced only in a digest-scoped managed install. The
installer verifies the original helper and Python member hashes before writing
the replacement and records `emuchievements-safe-arm64` in the receipt. A
changed archive and altered bundled helper or Python hash fail before install.

The [vendored source and rebuild recipe](../../ui/vendor/emuchievements-2.0.5/README.md)
include the upstream commit, pinned submodules, corresponding license files,
and local safety changes. On 2026-10-29, both networkless Docker rebuilds
matched the bundled binaries byte for byte:

| Architecture | Rebuilt SHA-256 |
| --- | --- |
| amd64 | `7a3430fa47d2321b93e0a9d1346c70ea920ae4d6f0766c04d5044122fed25e07` |
| ARM64 | `c492ed3b3ea3bdacbd5d530958c455a0d6928e8c51ae28a739b616ce164874b6` |

The published Decky 3.3.0 loader discovered the managed plugin in a private
network and device isolated amd64 container. Its legacy public `hash` RPC
returned the expected MD5 for a synthetic direct ROM and a ZIP containing that
ROM. A shell-like filename was passed literally. Traversal, absolute member
and symlink ZIPs failed; no extraction directories or escape files remained.
The local host transaction installed and removed the exact archive and checked
the managed receipt, helper hash, source hash, and executable mode. These tests
used no user's ROM, account, Steam library, or headset.

An isolated fake Frame HTTP/SSH e2e flow also installed and removed all pinned
official fixtures, including Emuchievements. The test checked its managed
receipt and both replacement hashes; the unique Docker project and volumes
were removed. This was a packaging test: fake Frame did not execute the
official backend. The earlier full 116-archive sweep was not rerun.

Hosted native ARM64 Decky, fake Frame e2e, and exact-head checks are required
before this change may merge. Real ROM formats, RetroAchievements login,
Steam page integration, real Frame managed backend execution, and worn VR are
unverified. The compatibility status is **partial** for the verified private
synthetic hash operation. An old managed copy retains the unsupported x86
helper until update or reinstall; its installed status remains **broken**.
