# Decky Localsend 0.4.5 native helper

The official Decky store ZIP SHA-256 is
`e271ccb55eb23f918b99a69f79aec905df4c9b2ef7b23bbf4ec1c2d1a6f0c6b7`.
Its Python backend matches upstream plugin tag `v0.45` byte for byte. That
tag pins LocalSend-Go commit `ad28b8e9440e17e44b4735a6c4aa0512009cf333`.
Building that source with Go 1.25.7, CGO disabled, `-trimpath`,
`-buildvcs=false` and `-ldflags='-s -w'` reproduces the published x86_64
helper **byte for byte**. The same source produced the ARM64 helper twice
with identical hashes.

| Artifact | SHA-256 |
| --- | --- |
| Official x86_64 helper | `d448d03861d578685e6c70ea3ace25eb34fca99cb9d4f98bf51ba23aa5cae843` |
| Rebuilt ARM64 helper | `e20363237e606ee65eae857792176d21a0bb8ba863489952728eaf2b13277dae` |
| `aarch64.gz` | `2c4e24dd00d67c6d4f2125b42f1eedc0fe8bcedcbf804be0c7ae91e7b391d5f9` |
| `source.tar.gz` | `f1f86292624b989d540689dbfad503bf15f3937d156978157b8dd418d54415d1` |

`source.tar.gz` is a Git archive of the exact LocalSend-Go commit, including
`go.mod` and `go.sum`. Go modules are **not vendored**: reproducing the
build requires access to checksum-verified dependencies or a populated module
cache. Run the following to check both expected helper hashes:

```sh
python3 scripts/build-framey-localsend.py \
  --go /path/to/go1.25.7/bin/go \
  --output /tmp/framey-localsend-build
```
The helper shipped to Frame needs no compiler, modules, root service or
runtime download. `LICENSE.txt` is the upstream MIT license; `GO-LICENSE.txt`
is the Go runtime BSD license. The official plugin ZIP retains its own
BSD-3-Clause license unchanged.

Only the exact official ZIP can use this managed adaptation. The Frame
transaction checks its original x86 helper and Python backend hashes,
checks the replacement ARM64 SHA-256 and ELF machine locally and again on the
headset, then records a managed receipt. Other native archives remain blocked.
The official x86 backend and the rebuilt ARM64 helper each passed a single
private no-route marker transfer. Published Decky 3.3.0 AMD64/ARM64 runtime
checks discovered the plugin and read its stopped status and configuration.
The actual managed Decky service on Frame, user-facing transfer, headset UI
and worn use remain unverified. See
`docs/evidence/framey-localsend-managed-2026-10-27.md` and its linked result.
