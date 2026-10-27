# Pinned Decky store test archives

These are unmodified ZIPs downloaded from the official Decky store CDN on
2026-10-25, except `96.zip` and `111.zip` downloaded on 2026-10-26 and `60.zip` on
2026-10-27; `13.zip` and `125.zip` were added from the digest-verified audit cache on 2026-10-27.
Each ZIP includes its upstream `LICENSE`. They are test data, not plugins shipped or installed by
Frame Control. The fake Frame tests serve them
from a local fixture so CI does not depend on the store being online.

| File | Official plugin | Version | Store SHA-256 |
| --- | --- | --- | --- |
| `13.zip` | Pause Games | 1.0.3 | `4aefdfb0ef25dea9c6d9fd037731c8b99ee8a1be966c2f7d5b0602112ef29f62` |
| `60.zip` | DeckyFileServer | 1.2.0 | `7dc2ecdcd05aa415d1ac90afaff28ecb17f77809a2bc7a77aee8e92505b976f0` |
| `125.zip` | Decky Localsend | 0.4.5 | `e271ccb55eb23f918b99a69f79aec905df4c9b2ef7b23bbf4ec1c2d1a6f0c6b7` |
| `96.zip` | Simple Timer | 1.0.0 | `973d927e9d9a1feec04679c564af7e389a729b6735d2a988ffc2cb46ce4eb312` |
| `7.zip` | CSS Loader | 2.1.3 | `99beaf1374af82408e6d056e0b0147e5fca544e1035fa7ab88419231697bc231` |
| `12.zip` | MusicControl | 1.1.6 | `246b89fd653c60a735b1cc401d1b0937d5cb969eea9024561661ff741f081d62` |
| `111.zip` | Music Control | 1.1.7 | `3f56a3f56034b277ea74a2c37cc84133b69e382aa6bcb0b43876776aac737ed9` |
| `14.zip` | ProtonDB Badges | 1.3.4 | `90a3453ac02709cad64096e7539fd8141fa56f99ae3441fc24a4990dc9684358` |
| `123.zip` | Steam Status | 1.2.3 | `9053308e04a74f44745b45b9f4f50af3673348d367e7b14bacc5677de707ac4e` |
| `50.zip` | Storage Cleaner | 1.4.0 | `1afa1a6f129c5d419de0e0bf0f6db8d8e50385a5659179346e996031ea372591` |
| `18.zip` | Bluetooth | 3.1.1 | `f07f7b74f31da15b5e3a8234a3f00faa01365b56b8f496aca7bb79120be7b8a5` |
| `26.zip` | HLTB for Deck | 2.0.12 | `bd54a23b0b8ec0798aa590e5be236522a593529d7680e77fb888e2971bf3d558` |
| `36.zip` | SteamGridDB | 1.8.1 | `e84f5b1f111af8862b06218479491fbf61036e1bfd9f16f93f9901e9b9ebc5e0` |
| `135.zip` | Deck Shelves | 2.0.0 | `b566280ad38fd3ecd584b5b46a855f301539eb9a86063834c64b7045f7063f91` |

The matching source projects include [Simple Timer](https://github.com/decktools-xyz/simple-timer) and
[CSS Loader](https://github.com/suchmememanyskill/SDH-CssLoader),
[MusicControl](https://github.com/nikurasu/MusicControl),
[Music Control](https://github.com/martinpl/music-control),
[ProtonDB Badges](https://github.com/bschelst/protondb-decky),
[Steam Status](https://github.com/bschelst/steamstatus-decky),
[Storage Cleaner](https://github.com/mcarlucci/decky-storage-cleaner),
[Bluetooth](https://github.com/Outpox/Bluetooth), and
[HLTB for Deck](https://github.com/morwy/hltb-for-deck),
[SteamGridDB](https://github.com/SteamGridDB/decky-steamgriddb), and
[Deck Shelves](https://github.com/santojon/Deck-Shelves).
The test verifies the ZIP digest, archive policy, API v1/v2 manifest, installed
frontend bytes, managed store receipt, and removal. Separate local host tests
start Bluetooth's frontend and its initial panel without running effects or
actions, and start HLTB's frontend and shallow settings view with a stub Steam
module lookup. They do **not** run plugin Python backends, Bluetooth actions,
HLTB searches, or prove JavaScript panels render in the VR shell. The
Bluetooth result and limits are in
[the fixture evidence](../../../docs/evidence/framey-bluetooth-fixture-2026-10-25.md).
Deck Shelves' chunked frontend renders its settings in local Chromium with
backend/network calls denied. Its Steam Home shelves cannot be verified in the
isolated VR panel; no worn-headset test is claimed.

Simple Timer also runs through actual published Decky 3.3.0 discovery, instance
RPC and events in the native isolated runtime gate. Cancel/replace/completion and
active/canceled/expired backend restarts are regression checks; the unmodified
archive must reproduce its historical lifecycle errors. Only private silent
timers/settings are used. The upstream BSD license stays unchanged.

Pause Games runs through actual published Decky 3.3.0 discovery and instance RPC
for private settings and a synthetic exclusion list. No process-control method
is called. The official frontend's standalone Toggle component separately
checks saved true/false state and matching settings callbacks; effects are inert.
DeckyFileServer also runs through actual Decky 3.3.0 discovery/API1 RPC with a
native helper replacement. HTTPS listing/download use only public markers in a
private directory; uploads remain disabled. The exact source build, GPL licenses
and reproducible recipe are in [the native assets](../../../ui/vendor/deckyfileserver-1.2.0/README.md).
The original empty optional-argument bug is reproduced by a negative runtime case.
Decky Localsend's exact original x86 backend/proxy passed an isolated private
marker transfer outside Decky. The native Decky gate checks discovery and
read-only backend status/configuration with its network helper stopped. The
managed ARM64 helper and transfer remain separately gated; the fixture does
not prove worn VR or a transfer on Frame.
