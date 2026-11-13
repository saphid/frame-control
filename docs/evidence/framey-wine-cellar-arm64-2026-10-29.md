# Wine Cellar 0.2.1 ARM64 feasibility, 29 October 2026

Wine Cellar **remains broken in Framey**. The official store archive contains
an x86-64 `bin/backend`, which the Frame Control installer correctly rejects
on ARM64. This investigation did not install the plugin, expose its panel in
VR, or change a Steam compatibility tool.

## Pinned inputs and local checks

The exact official 0.2.1 ZIP has SHA-256
`7e077b933c234414d172b5c6d1c804b026bf39fa4e18e6663495a282637031e8`.
Its `main.py` matches upstream tag `0.2.1` at commit
`8bf8e718a5f0d13cf27ee6e45191fae7d10c312f` byte for byte. The published
`bin/backend` has SHA-256
`7796bfc96d466824617b2fee96dc1bc4beda30c776a9c61e0cc168d3473d29fe`;
the published `dist/index.js` has SHA-256
`51ffdf606e0e307f46ea45828eb94f24ce75c44ccce5f55f696aa7aec89924b6`.

The upstream Rust suite passed **40/40** tests from that tag with its locked
dependencies. A local cross-build used Rust 1.98.1 on Debian Bookworm,
`gcc-aarch64-linux-gnu`, `libc6-dev-arm64-cross`, the
`aarch64-unknown-linux-gnu` target, and `LZMA_API_STATIC=1`. The resulting
3,216,136-byte ARM64 ELF has SHA-256
`d668a9ac02ccce97cf601bcff86f0b2104ee85e6a1105499e66178d9d19b64a8`.
This binary is a feasibility artifact; it is not shipped by Frame Control.

## Locked Frame probe

The probe acquired `/tmp/frame-test.lock` on the Frame with a unique owner
token before reading device state. SteamVR activity was **3 (standby)**,
proximity was **2.3125**, and battery was **100%**. There was no reliable wearer
confirmation, so the probe did not wake the Frame, send VR input, or run the
worn-check script.

Under that lock, the ARM64 binary ran against a private fake Steam home and a
loopback-only WebSocket tunnel. A read-only `GetState` request returned
`UpdateState` with zero installed tools. No real Steam tool directory or user
service changed. The runner removed its private files and processes and
released only its own lock. A second, separately locked audit found no matching
temporary directory or process; battery remained 100%.

## Remaining boundary

The Rust service accepts only `Origin: https://steamloopback.host` at
`127.0.0.1:8887`. A Framey plugin iframe has an opaque origin. Permitting that
origin directly would let unrelated opaque pages reach the helper's install
and uninstall commands. A future adaptation needs a receipt-bound, bounded
message bridge and an actual official frontend/backend test before the store
may accept the archive or the compatibility label may improve. Worn panel
visibility, physical controller input, tool installation and removal, and
user-facing behavior remain unverified.
