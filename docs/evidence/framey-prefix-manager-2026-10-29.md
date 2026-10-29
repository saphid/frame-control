# Games Prefix Manager: scoped user-service compatibility

Official store ID **130**, version **1.0.1**, archive SHA-256
`ef8c727943188cad04c63fae7e4e620b8080c07f35dec0c144e99c6166307473`.
The 2026-10-29 official store refresh returned 116 visible plugins; every
catalog version and digest was unchanged. Source:
[GamesPrefixManager](https://github.com/Saad-Alareqi/GamesPrefixManager).
The original GPLv3 license is preserved in the pinned test ZIP and installation.

## Change and limits

The official archive requests root and hard-codes `/home/deck` and
`/run/media/deck`. Its library parser expects an obsolete Steam VDF format.
The Python backend only needs the user's files; the exact managed archive now
runs without root, using Decky 3.3.0's exported `DECKY_USER_HOME` and `DECKY_USER`.
It retains the **unversioned legacy** manifest and calling convention.

The adaptation reads nested Steam `path` entries and checks cached app-ID
prefix paths against current library compatdata roots before deletion.
Prefix or compatdata symlinks are refused. Backups refuse nested symlinks and
special files, and use separate filenames rather than overwrite older backups.
A failed backup preserves the prefix. The panel reports backend refusals and
RPC errors through its toaster. Removal remains the normal managed operation.

This remains **partial**. No actual Steam prefix was deleted or backed up on
Frame. Complete non-Steam shortcut parsing, live Frame panel controls,
wearer-visible rendering and physical controller/keyboard input are unverified.
Symlink prefixes cannot be managed by this adaptation. The upstream prefix
scanner and its orphan classification have not been exhaustively validated
against real libraries; synthetic orphan cleanup is not a real-save safety claim.
The managed copy needs the `prefix-manager-user-paths` receipt marker;
older receipts retain a broken label until Update/reinstall.

## Published Decky discovery and RPC

The native runtime gate installs the exact ZIP through the production
transaction and starts the published **Decky v3.3.0** executable as an
unprivileged container user. It uses public `loader/get_plugins` and
`loader/call_legacy_plugin_method`; it never constructs `Plugin` manually.
The container has no network, devices, session bus or host home/Steam mounts.

The x86_64 pass verifies an empty initial list, a regular prefix and orphan in
two disposable libraries, backup contents, deletion and orphan cleanup. A
second backup for the same app ID preserves the first. Traversal, a root
symlink, nested backup symlink and replaced compatdata symlink are refused;
independent marker readbacks confirm unrelated data survives. The new case is
also included in the repository's native ARM64 CI gate; its result must be
checked separately before a green handoff.

```sh
python3 scripts/framey-test-decky-runtime.py --case 130 --output /tmp/prefix-runtime.json
```

## Local Chromium with the actual backend

The managed legacy bundle ran in Framey's opaque `allow-scripts` iframe, with
the repository React and host runtime. Its RPCs reached a separate published
Decky 3.3.0 x86_64 container containing only synthetic prefixes. External
network was denied. Passed:

- Open the prefix modal, filter by game name, cancel a deletion confirmation.
- Backup-and-delete a selected disposable prefix; clean a disposable orphan.
- Display a symlink backup refusal and retain the affected prefix.
- Reopen the modal and observe the backend's remaining list.
- Independently read both ZIP backups and verify their marker bytes; preserve
  the unrelated prefix and outside marker.

Shared T3 preview automation was unavailable due to this host's AppArmor
restriction, so the installed local Chromium was used. These are local browser
results, with a disposable backend, not Frame UI or controller evidence.

## Real ARM64 Frame, read-only

At 2026-10-29 21:19 UTC, the test acquired `/tmp/frame-test.lock` with an owned
random token. It started only a private, bounded, removable user service with
the digest-verified published ARM64 Decky v3.3.0 binary:
`8ef5dcf36cbbbb6e97201a6baed5d79c4cc44ec27789fc9af1c5b6ae8f0b25b6`.

Discovery and `get_games` ran through Steam CEF's normal `DeckyBackend.call`
bridge. Discovery returned the expected 1.0.1 plugin and the read-only list
contained **33 regular prefix directories**, all numeric app IDs. Only counts
were returned for evidence; game names, IDs, paths and save contents were not
published. No prefix-changing RPC ran. No wake or power-setting operation ran.

The private service, base, unit and uploaded ZIP were removed before releasing
the lock. Managed Decky and panel services were inactive before and afterward;
battery stayed **100 → 100**. The user's backup directory remained absent.
A separate locked cleanup audit found no private files, loaded units or upload
artifacts. No worn-VR or physical-input test was performed.
