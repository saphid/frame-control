# Games Prefix Manager upstream v1.0.2 preflight

On 2026-10-30, the live Decky store still served ID 130 **1.0.1** with
SHA-256 `ef8c727943188cad04c63fae7e4e620b8080c07f35dec0c144e99c6166307473`.
The separate [upstream v1.0.2 release](https://github.com/Saad-Alareqi/GamesPrefixManager/releases/tag/v1.0.2)
publishes `games-prefix-manager.zip` with GitHub asset digest
`12ab420f06023cd13717489aa92a1babd09dec8566a601f4b4bb93464fbc92b6`.
The downloaded bytes matched it. This preflight does **not** claim that the
Decky store offers v1.0.2 or that users can select it in Framey today.

The v1.0.2 ZIP has a lowercase `games-prefix-manager` folder, an unversioned
legacy manifest, and an unchanged `root` request. Its Python source still
hard-codes `/home/deck` and `/run/media/deck` and uses an obsolete library VDF
parser. It adds `delete_game_folder`: the upstream backend calls `rm -rf` on
an `install_path` derived from Steam metadata. Its own forbidden-path list
does not bound that path to a selected library. The release ZIP omits a
`LICENSE`; the GPLv3 file from the upstream v1.0.2 tag has the same SHA-256
(`4783d347807a864a7b10d34b3e82cf3a668143d855b31bc6dfd1d7e14d17674c`)
as the license in the store's v1.0.1 ZIP and is retained beside this test ZIP.

## Managed scope

Only the two exact archive digests get the user-service adaptation. The
v1.0.2 copy removes the root request, uses Decky's actual user home and current
Steam library paths, and keeps the existing prefix validation, non-overwriting
backups, ambiguous-ID refusal, symlink refusal, and disabled orphan cleanup.
It hides the new game-data checkbox and rejects `delete_game_folder=true` at
the backend before a backup or prefix deletion. The older 1.0.1 store copy
retains its own pinned behavior. A changed ZIP does not inherit either
exception.

## Verification

- `test_frame_decky_store.py`: the exact v1.0.2 ZIP passed archive checks,
  managed install/remove, Python compile, receipt and frontend transformation;
  a changed ZIP was rejected. All 55 store tests passed locally.
- In a network- and device-isolated container, published Decky **3.3.0**
  x86_64 discovered both pinned versions and answered the real legacy RPCs.
  The v1.0.2 fixture sent `delete_game_folder=true` and independently checked
  that the private prefix marker survived and no backup was made. Its existing
  disposable prefix backup/delete and refusal checks also passed. No host
  Steam files were mounted.
- A local Chromium 141 run loaded the exact managed v1.0.2 frontend in an
  opaque Framey iframe. An in-memory `Private Game` row appeared; the delete
  confirmation had no **Delete Game Data** control and orphan cleanup was
  unavailable. Backend writes and network were blocked. See the
  [browser capture](framey-prefix-manager-102-browser-2026-10-30.png).
- T3's shared browser returned `Authentication required` twice, so this
  browser observation used isolated local Chromium instead. Native ARM64 and
  exact-head CI results must be checked separately before merge.

The v1.0.2 backend has not been installed on a real Frame. Real Steam prefix
changes, game-data deletion, complete non-Steam names, a live Steam library,
wearer-visible panels and physical controller use remain unverified. These
checks do not raise the published v0.4.56 store classification for 1.0.1 or
authorize a release.

A subsequent native matrix found a forced v1.0.2 shutdown despite successful
RPCs. See the [scoped EOF repair and strict lifecycle evidence](framey-prefix-manager-102-ipc-eof-2026-10-31.md).
The preflight above does not establish clean shutdown. Store 1.0.1 claims remain unchanged.
