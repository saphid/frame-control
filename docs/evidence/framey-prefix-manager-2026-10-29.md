# Games Prefix Manager: scoped user-service compatibility

Official store ID **130**, version **1.0.1**, archive SHA-256
`ef8c727943188cad04c63fae7e4e620b8080c07f35dec0c144e99c6166307473`.
The 2026-10-29 official store refresh returned 116 visible plugins; every
catalog version and digest was unchanged. Source:
[GamesPrefixManager](https://github.com/Saad-Alareqi/GamesPrefixManager).
The original GPLv3 license is preserved in the pinned test ZIP and installation.
Scoped machine-readable results are in
[`framey-prefix-manager-2026-10-29.json`](framey-prefix-manager-2026-10-29.json).

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
RPC errors through its toaster. Because the published panel identifies a row
only by app ID, IDs appearing in multiple cached rows are rejected without
creating a backup or deleting any prefix. Removal remains the normal managed operation.

Automatic orphan cleanup is **disabled**, including direct RPC and stale cached
lists. The upstream non-Steam parser reads only the first Steam user's shortcut
file and silently accepts read/parse failures. Missing metadata therefore cannot
prove that a prefix is unused. The adaptation bypasses that parser and labels
unmatched prefixes **Unidentified prefix (may still be in use)**, never Orphan.
The panel disables its bulk cleanup control and explains the incomplete shortcut
coverage. Explicitly selected per-prefix backup/delete remains available.

This remains **partial**. No actual Steam prefix was deleted or backed up on
Frame. Complete non-Steam shortcut parsing, live Frame panel controls,
wearer-visible rendering and physical controller/keyboard input are unverified.
Symlink prefixes cannot be managed by this adaptation. Automatic orphan
classification and cleanup are intentionally unavailable. Unidentified prefixes
may belong to another Steam user or an installed non-Steam game.
The managed copy needs the `prefix-manager-user-paths` receipt marker;
older receipts retain a broken label until Update/reinstall.

The full 116-archive fake-Frame HTTP/SSH audit also checks managed receipt,
exact transformed frontend bytes and removal. Its assertions now distinguish
the pinned managed frontends for Storage Cleaner, DeckyFileServer and this
plugin from their original ZIP bytes; other archives still require identical
upstream frontend bytes. No plugin backend runs in that harness.

## Published Decky discovery and RPC

The native runtime gate installs the exact ZIP through the production
transaction and starts the published **Decky v3.3.0** executable as an
unprivileged container user. It uses public `loader/get_plugins` and
`loader/call_legacy_plugin_method`; it never constructs `Plugin` manually.
The container has no network, devices, session bus or host home/Steam mounts.

The x86_64 pass verifies an empty initial list, a regular Steam prefix and unidentified prefix in
two disposable libraries, backup contents and explicitly selected deletion.
It also verifies that cleanup returns zero removals, gives an actionable refusal
and never creates backups, even with a valid shortcut in the second Steam user's
file, malformed data in either file, unreadable data, no shortcut files, or
metadata changed after listing. Independent save-marker readbacks prove the
protected prefix survives. The fixture failed against the earlier implementation
because unmatched prefixes were incorrectly labeled Orphan. A second
backup for the same app ID preserves the first. Traversal, a root symlink, nested backup symlink and replaced compatdata symlink are refused;
independent marker readbacks confirm unrelated data survives. The new case is
also included in the repository's native ARM64 CI gate; its result must be
checked separately before a green handoff. The earlier cleanup repair passed
all 12 hosted checks at `3406610`, including native AMD64 and ARM64.

The duplicate-ID fixture creates different save markers for the same app ID
in two libraries. Sending the second row's ID refuses both backup modes and
preserves both markers without creating a backup. The fixture reproduced
the earlier wrong-prefix deletion (`[true, "Success"]`) before the guard.
After removing one disposable duplicate and refreshing, explicitly selected
deletion works again.

```sh
python3 scripts/framey-test-decky-runtime.py --case 130 --output /tmp/prefix-runtime.json
```

## Local Chromium with the actual backend

The managed legacy bundle ran in Framey's opaque `allow-scripts` iframe, with
the repository React and host runtime. Its RPCs reached a separate published
Decky 3.3.0 x86_64 container containing only synthetic prefixes. External
network was denied. Passed:

- Open the prefix modal, filter by game name, cancel a deletion confirmation.
- Backup-and-delete a selected disposable prefix.
- Show the disabled **Orphan Cleanup Unavailable** control and unidentified-prefix
  warning; refuse a direct bulk-cleanup RPC and preserve the unidentified prefix.
- Display a symlink backup refusal and retain the affected prefix.
- Reopen the modal and observe the backend's remaining list.
- Select the second of two same-app-ID library rows, verify the ambiguity
  refusal for both backup modes, and independently read back both save markers
  and the unchanged backup count.
- Independently read the ZIP backup and verify its marker bytes; preserve
  the unidentified prefix, unrelated prefix and outside marker.

Shared T3 preview automation was unavailable due to this host's AppArmor
restriction, so the installed local Chromium was used. These are local browser
results, with a disposable backend, not Frame UI or controller evidence.

## Real ARM64 Frame, read-only

At 2026-10-29 21:19 UTC, the test acquired `/tmp/frame-test.lock` with an owned
random token. It started only a private, bounded, removable user service with
the digest-verified published ARM64 Decky v3.3.0 binary:
`8ef5dcf36cbbbb6e97201a6baed5d79c4cc44ec27789fc9af1c5b6ae8f0b25b6`.

This real-device read-only check used the earlier implementation,
before automatic orphan cleanup was disabled. It verifies user-service discovery
and listing on ARM64, not the later classification/refusal behavior. No new
headset check was needed for the fail-closed repair; that repair is exercised in
the disposable published-loader fixture and included in the native ARM64 CI gate.

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
