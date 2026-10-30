# Game Sync read-only selection boundary, 30 October 2026

Official **Game Sync 1.0.4**, store ID **104**, has archive SHA-256
`65e021ebb37d2ebfbfbe3dbc8af95aef9556cf484730362c6b26c4ecc3e62ccd`.
Its original `py_modules/utils.py` SHA-256 is
`f17be1aabb2cf2a886a96ea4b57ad3390871979db398d48824e45dbc1113404b`.

The published `test_syncpath` checks a string prefix before counting files.
With a configured root named `saves`, it accepts `saves-other/private.bin`,
`saves/../saves-other/private.bin` and links leading outside the root. Three
private contracts reproduce **five failed refusal assertions** against the
exact original utility. No cloud request, subprocess or user file is involved.

Only this exact archive receives `game-sync-bounded-selection`. Its managed
utility resolves the configured root and selected paths, checks actual path
ancestry, and applies that boundary while counting a recursive selection.
Links within the root remain usable. A directory link back to an ancestor is
refused; shallow `/*`, recursive `/**`, single-file and missing-file behavior
are covered. The count still returns `-1` after more than 9,000 files.

The frontend, manifest, license, main backend, rclone manager and sync runner
remain byte-identical. Existing managed copies require Update/reinstall; their
receipt must contain the new shim before the store describes the fix as applied.

## Verification

- Full local regression: **1,776 tests, 16 skips, zero failures**, in
  **214.137 seconds**. These platform/tool skips are not hardware verification.
- Six installed-utility contracts pass with only private temporary paths.
  Outside fixture bytes remain unchanged after every contract.
  The exact install and all six contracts also pass under Python 3.9 in a
  read-only, network-isolated container.
- The managed transaction verifies exact-digest scope, receipt, preserved
  payloads and successful removal. A changed archive receives no adaptation.
- [Published Decky 3.3.0 x86_64 evidence](framey-game-sync-selection-native-2026-10-30.json)
  verifies real discovery and RPCs for valid file/shallow/recursive selections,
  in-root links, sibling and parent escapes, outside file/directory links and
  a recursive directory cycle. Independent file reads preserve the outside
  marker. The configured boundary and refusal survive an actual loader restart.
  The report records installer/probe source hashes.
- Native execution uses an unprivileged, network- and device-isolated disposable
  container, with no host session or writable host bind mount. The harness
  removes its container and image.
- Three fake-Frame HTTP/SSH transport regressions pass in **73.844 seconds**:
  reset, install/update/remove safeguards, and all pinned official installs and
  removals. They check the new receipt and unchanged rclone manager; official
  backend execution is stubbed in these transport tests. The owned project
  `framey-game-sync-87951f56d1`, both containers, network and three named volumes
  were removed. Compatibility lookup and runtime probe inventory checks pass.

## Limits

This is a **read-only selection check**, not an execution sandbox. It does not
change or validate the paths rclone later copies, prevent filesystem changes
between lookup and execution, or prove cloud synchronization. The original
default sync root is `/`, and default rclone arguments include `--copy-links`.
Its updater still downloads an unpinned amd64 rclone archive. Process-signal
RPCs and shared bisync-lock cleanup also remain unchanged and unverified.

Game Sync stays **partial**. The revised ARM64 selection fixture, actual
cloud authentication/sync, browser controls, real Frame managed execution,
wearer-visible rendering and physical controllers remain unverified. No real
Frame was contacted; the separate headset schedule retains that work. No
release is included. New exact-head CI/e2e/native runtime must pass before merge.
