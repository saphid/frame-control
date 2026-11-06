# User-owned NxNative game sources

Frame Control includes **no game repository, ROM download URL, ROM, title key or
console key**. Add your own source under **Android apps → NxNative games**. Source
settings and catalog snapshots stay in this computer's private app-data folder;
they are not added to the public APK catalog or compatibility database.

You can add:

- An HTTP(S) JSON catalog, UTF-8 URL list, or EmulationStation `gamelist.xml`.
- A local folder, including an SMB, NFS or WebDAV share already mounted by the
  computer's operating system. On Windows use the mounted drive or UNC path; on
  macOS use its path under `/Volumes`; on Linux use its mount path.
- A prepared build folder containing `game.apk`, `patched_android`, `shader/vk`,
  `font` and exactly one `extract/*/RomFS` directory.

For a completed build on a local disk or mounted share, add that exact build
folder to avoid exporting and copying a multi-gigabyte ZIP. To share prepared
games online or across computers, use the versioned JSON catalog below with
`.nxnative.zip` files and their SHA-256 checksums. A library folder without a
catalog is scanned recursively for raw ROM files and `.nxnative.zip` files;
prepared build subfolders need their own source or an explicit `build` entry in
the catalog.

The list distinguishes **Prepared build** from **Preparation required**. A raw
NSP/XCI library is useful for browsing, but raw ROM files are not Android apps.
The preparation action explains the exact Mac tools and matching game inputs
needed. It does not pretend arbitrary games or versions can be converted.

The builder verifies modules against each game's exact profile, including games
with `main`/`sdk` and no `subsdk0`. The bundled Celeste 1.4.1.1 metadata is for
experimental bring-up: visible gameplay, remote movement/jump input, audio and
cold save reload were observed on Frame, including after the shared renderer
update. Exact release-candidate checks, physical controller feel and
worn-headset comfort remain unverified. Its MGFX
shader packages also need the newer upstream extraction tool described in the
[profile notes](../frame/nxnative/profiles/01002B30028F6000/README.md).

For extracted games with a compatible LÖVE `main.lua`, the separate
[LÖVE packager](../frame/love/README.md) produces a private APK installed through
the normal Android installer. The preparation guide includes this separate route
and an **Install a prepared APK** button. Choose **Choose a file** to select an
APK, including one on a share mounted on your computer. The installer's link
option accepts public HTTPS APK downloads, not private LAN URLs. These APKs
contain the user's game assets and must stay out of Frame Control release
assets. NxNative catalogs do not prepare or
install them as `.nxnative.zip` bundles.

## Existing formats and the chosen boundary

| Format / service | What it provides | This version |
|---|---|---|
| [EmulationStation gamelist.xml](https://github.com/Aloshi/EmulationStation/blob/master/GAMELISTS.md) | Existing local game paths and metadata, with `gameList/game/path` and `name` | Read those paths/names. Raw ROMs need preparation; paths to portable NxNative bundles are installable. |
| UTF-8 URL list | A simple list understood by many download tools | Read one URL/path per line; ignore empty lines and `#` comments. Raw ROM entries need preparation. Prepared online bundles need a JSON catalog with SHA-256. |
| [RomM](https://github.com/rommapp/romm) | A maintained, self-hosted ROM library and API, with its own authentication and metadata | A good future server adapter. Native RomM login/API synchronization is not implemented; use an exported catalog or mount its library folder. |
| DAT / MAME software lists | ROM identity, expected files and checksums, rather than a portable installation or download-repository protocol | Not treated as a download source. A DAT alone does not identify a URL or the matching NxNative rewrite/shader outputs. |
| [WebDAV (RFC 4918)](https://www.rfc-editor.org/rfc/rfc4918) | Standard HTTP collection/property operations; it is a transport, not a ROM metadata schema | Mount a WebDAV share on the desktop, or serve a catalog and bundles over HTTP(S). No built-in PROPFIND client. |
| SMB / NFS | Authenticated network filesystems managed by the operating system | Add a mounted folder. Frame Control does not mount shares, store SMB passwords or install a filesystem client. |

The formats above do not describe the complete NxNative installation: executable
rewrite, Vulkan shaders, fonts, package identity and atomic data publication.
A small versioned JSON catalog and portable build manifest supply that missing
part while reusing existing gamelist paths and transports.

On iPhone/iPad, a prepared HTTP(S) catalog works without a Mac builder online.
The source server runs on the Frame, so a local source must be mounted on the
Frame and use its path there. A phone Files location or a desktop mount path is
not automatically available to that server.
Native SMB/WebDAV browsing, HTTP login forms, automatic RomM synchronization,
raw-ROM downloads and remote Mac build orchestration remain future work.
Embedded usernames/passwords in URLs are rejected. Use a mounted authenticated
share, or an HTTP(S) endpoint your app can access. Prefer HTTPS for online sources.

## JSON catalog

Create `nxnative-catalog.json` (a folder also recognizes `catalog.json`,
`gamelist.xml` and `urls.txt`, in that order). The catalog can contain relative
paths/URLs, which resolve against its own location:

```json
{
  "format": "frame-control-nxnative-1",
  "games": [
    {
      "id": "my-prepared-game",
      "name": "My game",
      "title_id": "010093801237C000",
      "version": "2.1.0",
      "bundle": "prepared/my-game.nxnative.zip",
      "sha256": "COPY_THE_64_HEX_DIGIT_SHA256_FROM_THE_EXPORT_RECEIPT"
    },
    {
      "id": "my-unprepared-copy",
      "name": "My original copy",
      "path": "originals/my-game.nsp"
    }
  ]
}
```

Replace the checksum placeholder before using this example. A prepared **online**
bundle without SHA-256 stays visible but cannot be installed. The checksum is
pinned by your source, rather than trusted from the Install request. For a local
prepared build folder use `"build": "./frame-build"` instead of `bundle`.

An online catalog may reference only HTTP(S) resources, never local paths or
`file:` URLs. Source removal removes the saved listing; it leaves installed games
and saves intact. A source that fails refresh shows its own error and loses stale
Install buttons, while other sources remain available.

## Prepare once on the Mac

The working Frame route uses the pinned NxNative Android/Vulkan fork. See
[the build instructions](../frame/nxnative/README.md) for its exact tools and
supported Dread module IDs. Dread 2.1.0 and the experimental Celeste 1.4.1.1
profile have physical Frame gameplay evidence; see the per-game limits in the
[device results](nxnative-on-frame.md#follow-up-validation-2026-11-06).

If your original copy needs extraction, the pinned fork's
[`nx_extract`](https://github.com/joaquinsandoval2307/nxnative/blob/32b0ef2c5408e1e32cb5c0bc49f84d1e63653dc3/dm/tools/nx_extract/Program.cs)
accepts your own `prod.keys`, base NSP/XCI, optional update NSP and output path.
Keys and game inputs stay on your build machine. Extracting alone is insufficient:
the game also needs a matching profile and shader package/cache. The app's
preparation guide states this requirement. It does not supply keys, extract from
an online ROM source or silently invoke decryption.

Append `--bundle /path/to/my-game.nxnative.zip --version 2.1.0` to the documented
`frame/nxnative/build.py` command. After rewriting, shader export, native build,
regression tests and APK signing, it exports the portable installer automatically.
To export an already completed build without rebuilding:

```sh
python3 ui/frame_nxnative.py export \
  --build /path/to/frame-build \
  --output /path/to/my-game.nxnative.zip \
  --title 010093801237C000 --name 'My game' --version 2.1.0
```

The command prints its path, SHA-256 and size. Add that local folder to the app,
or put the ZIP and JSON catalog on your own HTTP server or mounted share. Export
needs free space for a second copy of the dataset; adding the completed local
build folder avoids that extra copy.

## What one Install does

The app resolves the selected entry from its saved source snapshot. For an online
bundle it downloads to app cache and checks the catalog SHA-256. It validates the
entire ZIP directory and manifest, rejects paths that escape staging, duplicate
names, links, encrypted members and extra files, and streams each payload through
its declared size and SHA-256 check. It then checks the APK's actual manifest
package against the bundle title ID and Android/ABI requirements.

Only after these checks does it install the per-game APK into the selected
Frame's persistent Lepton instance. A fresh container installs the updated APK;
the game process is stopped before data transfer. The importer copies GNU-format
archive records, verifies every file inside Android, and atomically switches the
versioned dataset pointer. The app then opens the ready game, which has its own Steam library entry. Private saves are outside the staged dataset.

A failed transfer leaves the previous data selection intact. The APK may already
have updated if a later headset transfer fails; retry the Install after fixing
the connection. This is not a transactional rollback of APK and game data together.
The app never deletes old game datasets or saves to reclaim space.

Portable ZIP format `frame-control-nxnative-bundle-1` has exactly:

- `nxnative.json`: format, name, title ID, version and `files` records with `path`,
  byte `size` and SHA-256.
- `game.apk`: the per-game ARM64 Android host.
- `data/dm`, `data/vk`, `data/font`, `data/romfs`: rewritten modules/fixups,
  SPIR-V/reflection, fonts and extracted game files.

Limits are 8 MiB for catalogs/manifests, 50,000 payload files and 64 GiB total
unpacked data. Bundles use ZIP64 and store payloads without an extra compression
pass. Local staging needs room for the extracted payload plus 128 MiB reserve.

## Validation

`python3 -m unittest discover -s tests -p test_nxnative_sources.py` checks private
source persistence, all supported catalog readers, mounted-folder discovery,
per-source failure isolation, HTTP download checksum rejection, exporter/importer
round trips, actual APK title identity, unsafe archive rejection, mutation order
and the selected headset's SSH route. The separate data-publication tests cover
bad checksums and interrupted uploads preserving the previous selection and saves.

The real app HTTP API and install queue were exercised on the Mac against the
physical Frame: add a prepared Dread build folder, install its APK, transfer and
verify 11,814 files (5,418,485,729 bytes), reopen the title, then remove the source.
The selected dataset was correct and all four save-file hashes stayed unchanged.
The first run caught an Android startup/storage race; the installer now waits
for boot, mounted storage and the package before transferring data.
[Physical installation receipt](evidence/nxnative-frame-app-install-2026-11-05.json).
