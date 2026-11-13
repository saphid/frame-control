# Wine Cellar 0.2.1 ARM64 candidate

`aarch64.gz` contains an ARM64 build of the exact upstream 0.2.1 Rust helper.
It is only selected for the official ZIP with SHA-256
`7e077b933c234414d172b5c6d1c804b026bf39fa4e18e6663495a282637031e8`.
The upstream source is MIT/BSD licensed; the official combined `LICENSE` is
included here. The published x86-64 helper remains in the official ZIP.

Source: https://github.com/FlashyReese/decky-wine-cellar at tag `0.2.1`,
commit `8bf8e718a5f0d13cf27ee6e45191fae7d10c312f`.
The upstream Rust suite passed 40/40 tests with its locked dependencies.

Build environment: Rust 1.98.1 Bookworm, `gcc-aarch64-linux-gnu`,
`libc6-dev-arm64-cross`, target `aarch64-unknown-linux-gnu` and
`LZMA_API_STATIC=1`. Build with:

```sh
cd backend
CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_LINKER=aarch64-linux-gnu-gcc \
  LZMA_API_STATIC=1 cargo build --locked --release --target aarch64-unknown-linux-gnu
```

The uncompressed 3,216,136-byte ELF SHA-256 is
`d668a9ac02ccce97cf601bcff86f0b2104ee85e6a1105499e66178d9d19b64a8`.
The deterministic gzip SHA-256 is
`7c06e4a6548db3961bfefd4053302b40dd3484cc9a63c852925453f1b38aeeb8`.
The exact helper answered read-only `GetState` against a private fake Steam home
on the real ARM64 Frame; see
[`docs/evidence/framey-wine-cellar-arm64-2026-10-29.md`](../../../docs/evidence/framey-wine-cellar-arm64-2026-10-29.md).

The managed `main.py` also installs Frame Control's child-local Decky 3.3.0
IPC EOF repair. Without it, the published loader can spin on a closed parent
socket, preventing Wine Cask's exit from being reaped before Decky's five-second
plugin stop deadline. The managed backend waits for its exact helper, bounds
TERM/kill waits, and stops its supervisor within that deadline. It does not patch
the global loader or change the Rust helper. Existing managed installations must
be updated or reinstalled to receive the `wine-cellar-ipc-eof` receipt marker.

The AMD64 read-only state, restart, open-socket unload and prior-source negative
control are recorded in
[`framey-wine-cellar-unload-2026-10-31.md`](../../../docs/evidence/framey-wine-cellar-unload-2026-10-31.md).
Fresh ARM64 lifecycle qualification and real Frame operation remain unverified.
