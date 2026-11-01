# Animation Changer override preservation

Animation Changer store ID 23, version 1.3.2, exact published ZIP SHA-256
`f2c62b90ca60d8a80b6d0f75d8027552b1509c7a05842c6f4a24a9072846d133`.
The original `main.py` SHA-256 is
`11a96a6f3108021b096e0aeb60c7d3ee3c6b2e237cf235c02f5753cf9d3382b8`.
This archive came from the existing digest-verified catalog cache. This is not
a fresh store metadata check.

The published `apply_animation` removes an existing override before checking
whether the selection is empty or whether the selected source exists.
Startup applies three initially empty selections. Executing the exact original
function against disposable sentinel files reproduced deletion of
`deck_startup.webm`, `steam_os_suspend.webm` and
`steam_os_suspend_from_throbber.webm`. No plugin startup, migration, Steam
session, network or pre-existing user file was used in that baseline.

The exact managed install keeps the original backend bytes and appends a
helper installation call. All other published archive members stay unchanged.
The helper limits writable names to those three videos, resolves a valid
source before changing the override, and leaves unmanaged overrides alone for
empty selections. On the first managed selection it moves the prior file or
symlink into a private sibling backup. Repeat/switch retains that same original.
Clearing a managed selection restores its original bytes, inode and symlink
text, or removes only the owned link if no prior override existed.

Ownership records include the target, installed symlink destination and inode.
A changed target, missing backup, malformed record, directory target, unknown
video name or linked backup directory is refused. A per-directory file lock
serializes managed changes. Tested metadata-write failures restore the prior
file or managed symlink without losing its identity.

## Verification

Sixteen focused tests execute the installed exact archive and installed helper
against disposable files, with all network/migration calls blocked. They cover
all three empty defaults; prior regular and broken links; repeat/switch/reset;
new helper instances reading persistent ownership; unknown/missing sources;
manual target replacement; missing backups; first/switch metadata-write
failures; path/name boundaries; self-reference; and exact installer delivery.

Published Decky 3.3.0 **native AMD64**, in a networkless, device-free container
with an owned temporary home, passed legacy discovery and **23 RPCs**. The
unchanged backend's startup preserved all three fixture overrides. Nine
apply/repeat/switch transitions and three resets retained the prior bytes and
inodes; the two selected source files were unchanged. An independent audit
checked all 28 runtime input hashes, installed backend/helper hashes, decoded
fixture bytes, transitions, RPCs and the retained console. The loader exited
zero with a parent-only signal and no forced kill. The generic recorder's
`cleanShutdownVerified` flag remains false; no separate strict restart/shutdown
proof is claimed.

Full local unit suite: **1,987 tests, 15 platform/dependency skips**. Site:
**18 tests, zero skips**. Full disposable fake-Frame suite: **53 tests, zero
skips**, all **116** pinned catalog archives, **69 install/remove and 47
expected refusal outcomes**. Independent post-run inspection found no owned
containers, volumes, networks, image tags or configuration file; the shared
simulator stayed healthy. The catalog suite does not execute official
backends. The final test-only change canonicalizes temporary paths for systems
where `/tmp` is a symlink; all **16 focused tests** pass after that correction,
plus **24 compatibility tests** and the generated-doc check. Native and e2e
production inputs are unchanged. Exact-final-head hosted CI remains required.
Existing socket ResourceWarnings remain. Compatibility remains **partial**. See the [summary](framey-animation-overrides-2026-11-01.json)
and [raw evidence and verifiers](framey-animation-overrides-2026-11-01-raw.json.gz).

## Using and recovering backups

Existing managed copies need **Update/reinstall**. Empty selections preserve
unmanaged files; the fix cannot recover files deleted by an older copy. Clear
managed selections before uninstalling if you want the previous movies restored.
The backup is under the actual user's resolved movies directory:
`.frame-control-animation-backups/<video-name>/original`.

When an external change or an incomplete transaction makes ownership uncertain,
the helper refuses to overwrite the current movie or backup. Preserve both and
inspect the ownership record before manual recovery. Do not remove the backup
directory as a cleanup step. Automatic recovery after abrupt process/power loss
is not implemented or verified, and external writers do not share this lock.

Native ARM64, legacy migration of real user files, repository downloads,
rendered controls, actual Steam video decoding/playback, real Frame use and worn
visual/controller behavior remain unverified. No real headset was contacted.
