# Game storage

Open **Tools → Game storage** for a read-only snapshot of the headset's user
filesystem and Steam libraries. Refresh after an installation, download or move.
The page never moves, deletes or modifies content, starts Steam, requests root,
or recursively scans game files. It works through the existing SSH connection.

## What the numbers mean

- **Total, free and used** come from `statvfs` on the headset user's home and
  each library path. Free is space available to that user; reserved blocks mean
  used + free can be less than total. These are filesystem sizes, not advertised
  drive capacity, and do not include separate system partitions.
- Libraries come from `~/.local/share/Steam/steamapps/libraryfolders.vdf` plus
  the default Steam library. Modern nested and older numbered-path records are
  accepted; canonical duplicate paths are shown once. No drive is mounted.
- Two paths can share one filesystem. Their capacity must **not** be added.
  An unmounted drive whose mount directory still exists can report the parent
  filesystem's capacity: the page labels this as the filesystem containing the
  path, rather than claiming the removable drive is connected.
- Game sizes are Steam's `SizeOnDisk` records in `appmanifest_<appid>.acf`, sorted
  largest first, with unknown sizes last. A missing, negative or invalid size
  is **Unknown**, while an explicit zero remains zero. Records may be stale,
  including during downloads or moves; they do not measure allocated blocks.
- Games/apps and runtimes/tools have separate subtotals of **known recorded**
  sizes. Runtime classification uses names (Proton, Steam Linux Runtime,
  Steamworks Common, FEX and Lepton Development), so it is only a convenience.
  Additional apps or runtimes may fall in the game/app group.
- Saves, Proton prefixes, shaders, workshops, downloads, Android apps,
  sideloaded games, media and OS files are **unmeasured other usage**. The page
  does not subtract manifest totals from filesystem usage to invent a size for
  them. Recorded content is not an exhaustive storage breakdown.

Permission denied, missing/disconnected paths, unavailable filesystem reads,
invalid metadata and partial inventories are reported separately. A failed read
is never proof of an empty library. If library discovery fails, other libraries
may be missing from the view. Refresh clears the old results immediately; a
headset switch clears the snapshot and ignores late replies from the old device.

## Moving a game safely

Use Steam's own **Settings → Storage** on the headset (or in desktop Steam):
choose the source drive, select the games and choose **Move**, then pick a
Steam-supported destination. A second Steam library must already be available.
Steam may withhold Move or a destination when it cannot perform the operation.
Let Steam finish, follow Steam's errors/recovery prompts, then Refresh here.
Do not manually delete files to make room or interrupt an in-progress move.

[Valve's moving guide](https://help.steampowered.com/en/faqs/view/4BD4-4528-6B2E-8327#move)
was read in a browser on 2026-10-24 and documents this UI. This is an instructional
handoff: the page does not send a URI or silently open a UI on the headset.
The guide's separate Windows instructions for moving the entire Steam client
are outside this feature's scope.

### Why Frame Control does not automate moving

The repository's Valve devkit tools register and launch developer titles; no
supported game-move operation is provided there. The existing Steam CEF bridge
uses internal client APIs, which are not a verified supported contract for a
move transaction. [Valve's public ISteamApps reference](https://partner.steamgames.com/doc/api/ISteamApps) provides install-directory
and installed-depot queries but no documented move transaction with completion,
cancellation, rollback and error guarantees. The public support guide describes
the user-operated Storage UI, rather than such an automation interface.

Consequently this feature adds no move endpoint or guessed internal Steam call,
manifest rewrite, copy/delete fallback, or custom rollback. Automating a move
requires a supported interface and verified behaviour for full disks, disconnects,
running games, downloads, cancellation and Steam restart first.

## Verification and limits

`tests/test_storage.py` runs the actual probe against temporary Steam metadata
and filesystem/error fixtures. It covers multiple libraries, duplicate paths,
zero/unknown/invalid sizes, corrupt manifests, unreadable directories and files,
missing discovery/drives, reserved capacity and read-only file preservation.
A loopback HTTP test executes the real guarded endpoint with SSH mocked.
`tests/storage.cjs` runs the production renderer, navigation and refresh handlers
with DOM/transport boundaries faked, including escaping, offline errors,
out-of-order refreshes and headset switches. It runs through unittest discovery.

The production storage component was rendered with synthetic data at 390px and
900px widths; both fit without horizontal overflow. This checks component
layout, not the full connected application or headset browser.

No storage probe, game move or other operation was performed on a real headset
for this change. UI and metadata fixtures are synthetic. Actual removable-media,
SteamOS UI and device permission behaviour remain to be checked under the shared
lock and battery/restore procedure in [testing.md](testing.md#headset-smoke-test).
