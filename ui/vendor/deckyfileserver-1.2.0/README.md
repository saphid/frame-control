# DeckyFileServer 1.2.0 native helper

The official store archive (`7dc2ecdcd05aa415d1ac90afaff28ecb17f77809a2bc7a77aee8e92505b976f0`)
contains an x86_64 helper. Frame Control replaces only that exact archive's
`bin/backend` with the native Linux helper here. No runtime download, compiler,
root service or system package is used.

Upstream: https://github.com/grimkor/DeckyFileServer
Pinned source commit: `dcf3f3ce5104d05811fa8c156c4f58632b84b313`.
The source tarball fetched from GitHub has SHA-256
`0854ca668b64598b0871ceda842912332b75e5c482afeea8a533e4cb38921639`.
Its `main.py`, `plugin.json` and `package.json` match the store ZIP byte for byte.
The published Go binary has no VCS revision metadata, so its source revision
cannot be independently established from the binary.

`source.tar.gz` is the complete corresponding helper source, embedded resources,
Go module metadata, vendored dependencies and their licenses, plus upstream
`LICENSE`. SHA-256:
`50d90a7328daa412bf963ec68bb4855a9ec0860a8475cdf7d2019e6c2507112d`.
It is available in the same app bundle/repository as these binaries. Upstream is
GPL-3.0; see `LICENSE.txt`. The statically linked Go runtime uses the BSD license
in `GO-LICENSE.txt` (toolchain source: https://go.dev/dl/#go1.25.7).

The sole Go source change replaces the fixed `/tmp/deckyfileserver.log` path
with `filepath.Join(os.Getenv("DECKY_PLUGIN_LOG_DIR"), "deckyfileserver.log")`,
falling back to `os.TempDir()` when the environment variable is empty. This keeps
managed and private test logs separate. The upstream HTTPS certificate/key are
public embedded test material, unchanged; this is not a trusted TLS certificate.

Reproduce offline with Go **1.25.7** and Python 3.12+:

```sh
python3 scripts/build-framey-fileserver.py --go /path/to/go1.25.7/bin/go --output /tmp/framey-fileserver-build
```

The script extracts only this source archive, disables module downloads, uses
`CGO_ENABLED=0`, `GOOS=linux`, `-mod=vendor`, `-trimpath`, `-buildvcs=false` and
`-ldflags='-s -w -buildid='`, and emits deterministic gzip assets (mtime 0).

| Architecture | Uncompressed helper SHA-256 | Gzip SHA-256 |
| --- | --- | --- |
| x86_64 | `5e90efd1bf5163bef1686045f4714ad0e4fd0f54edb037fce8cdb06c58177bcb` | `84e49f049bbc475bc553ef52adc05dcd323e36c5f5ec75008558ae87f3a0e6d7` |
| aarch64 | `86b80021ebd62ed619eba065757c1122defa5a74b2c045aa44a0c6b4403a508a` | `7ca1b8aebd4e8d2c8ce382ca561e1413ad8e581f85f419a1da777c87d86c4a19` |

The managed Python adaptation removes only this digest's `_root` flag, handles
unavailable hostname DNS,
filters omitted flags and applies thumbnail policy before server startup.
The server still shares the selected directory on all interfaces using the
upstream self-signed HTTPS server; it has no authentication. Select only a
directory you intend to share. Uploads remain off by default. Protected system
files remain subject to the ordinary Frame user's permissions.
