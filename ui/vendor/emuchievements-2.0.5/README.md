# Emuchievements 2.0.5 managed native helper

The unmodified official Decky ZIP is pinned at SHA-256
`98dcb443e81b9f9011cfe77c69eb659869c8e2df2df8b0a443df66cbfc2f5a89`
in `tests/fixtures/framey-official/28.zip`. Its x86 helper and Python entry
point cannot be used as-is on Frame. The installer accepts the exception only
for that complete ZIP digest and checks the original members before replacing
them. The managed receipt records `emuchievements-safe-arm64`.

The corresponding source archive, `source.tar.gz`, contains EmuDeck's
[Emuchievements](https://github.com/EmuDeck/Emuchievements) source at commit
`8567e94befffc943434b2adb842487274815f8bb`, including its pinned
submodules and the local changes to `backend/src/util.cpp`, `util.h`,
`main.cpp`, and `src/py/main.py`. The upstream project license is in
`LICENSE.txt`; the source archive retains the dependency license files.
The archive also includes `FRAMEY-CHANGES.patch`. The submodule commits are
libarchive `b3be94ba4f36943745e64a6a0a3c21c2d1281d3c`, libchdr
`a20e04c12c0c20048bf771da6df7aa2e51f5e0cb`, and rcheevos
`85a3209398e576d79170f569fcddf277640f3f06`.
The local changes bound archive extraction, reject unsafe members and paths,
remove only the helper's private temporary directory, handle hash failures,
and invoke the helper without a shell or shared `/tmp` log.

| Asset | Uncompressed SHA-256 |
| --- | --- |
| `source.tar.gz` | `74b98fe484af0d50d3b5fdf3c478c260a6dcb20773dceea3cb4d7961a80c51a1` (archive bytes) |
| `main.py.gz` | `2a99670f10d43008af66d760aaab51f4c44b1ff2e8de73627df38b1bd30cdb90` |
| `x86_64.gz` | `7a3430fa47d2321b93e0a9d1346c70ea920ae4d6f0766c04d5044122fed25e07` |
| `aarch64.gz` | `c492ed3b3ea3bdacbd5d530958c455a0d6928e8c51ae28a739b616ce164874b6` |

Build the two disposable Bookworm images from `Bookwormfile` and
`BookwormCrossfile`, then run the verification script with those image names:

```sh
docker build -f ui/vendor/emuchievements-2.0.5/Bookwormfile -t framey-emu-bookworm ui/vendor/emuchievements-2.0.5
docker build -f ui/vendor/emuchievements-2.0.5/BookwormCrossfile -t framey-emu-bookworm-cross ui/vendor/emuchievements-2.0.5
python3 scripts/build-framey-emuchievements.py \
  --amd64-image framey-emu-bookworm \
  --arm64-image framey-emu-bookworm-cross \
  --output /tmp/framey-emu-rebuild
```

The script verifies the source tarball SHA-256, builds in networkless,
device-free containers, and compares both binaries byte for byte with the
bundled assets. The actual Decky runtime gate tests only private synthetic
direct and archived ROM files. Real ROM formats, RetroAchievements login,
Steam UI integration, real Frame execution, and worn VR remain unverified.
