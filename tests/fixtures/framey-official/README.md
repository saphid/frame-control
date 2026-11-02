# Pinned Decky store test archives

`37.zip` was downloaded from the official CDN on 2026-11-01 and matched the existing catalog digest. This is not a fresh full-store metadata claim. Its private IPC tests use a disposable local wire peer; no real Discord account or Frame is contacted.

These are unmodified ZIPs downloaded from the official Decky store CDN on
2026-10-25, except `96.zip` and `111.zip` downloaded on 2026-10-26 and `60.zip` on
2026-10-27; `13.zip` and `125.zip` were added from the digest-verified audit cache on 2026-10-27,
and `67.zip` and `114.zip` on 2026-10-28. `24.zip`, `28.zip`, `52.zip`, `79.zip`, `93.zip`, `104.zip`, `118.zip` and `132.zip` were added on 2026-10-29.
`130.zip` was added from the same digest-verified cache on 2026-10-29; a fresh
official store read confirmed all 116 catalog version/digest records unchanged.
The store ZIPs include their upstream `LICENSE`. The separate upstream v1.0.2
GitHub release ZIP omits it; `130-v102.LICENSE` is the GPLv3 file from its
tag, byte-identical to the license in `130.zip`. These are test data, not plugins shipped or installed by
Frame Control. The fake Frame tests serve them
from a local fixture so CI does not depend on the store being online.

`117.zip` was added from the digest-verified static audit cache on 2026-10-30.
A fresh official store read confirmed DeckyParty 1.0.0 and the same digest.

`134.zip` was downloaded from the official CDN on 2026-10-31 and matched the existing catalog digest. This is not a fresh full-store metadata claim.

| File | Official plugin | Version | Store SHA-256 |
| --- | --- | --- | --- |
| `37.zip` | Discord Status | 1.5.0 | `00a45dd919abb6e050685e1e408ce8023b9c4a09d6e91ba528d50aed2a63bf45` |
| `23.zip` | Animation Changer | 1.3.2 | `f2c62b90ca60d8a80b6d0f75d8027552b1509c7a05842c6f4a24a9072846d133` |
| `134.zip` | Deck Progress Tracker | 1.3.6 | `784c59e7e2a344eb6803d00e341c7d5f10d42cea7b60cc4332f4c3687db14fb3` |
| `117.zip` | DeckyParty File Manager | 1.0.0 | `193fb3aa0446fbc3c6bae0ae15700b5f04acebfa917b8e1791988c6ce832dddf` |
| `130.zip` | Games Prefix Manager | 1.0.1 | `ef8c727943188cad04c63fae7e4e620b8080c07f35dec0c144e99c6166307473` |
| `130-v102.zip` | Games Prefix Manager upstream GitHub release asset; **not in the Decky store on 2026-10-30** | 1.0.2 | `12ab420f06023cd13717489aa92a1babd09dec8566a601f4b4bb93464fbc92b6` |
| `13.zip` | Pause Games | 1.0.3 | `4aefdfb0ef25dea9c6d9fd037731c8b99ee8a1be966c2f7d5b0602112ef29f62` |
| `24.zip` | RadiYo! | 1.3 | `647111578aa7a5ecd16af8d7fe6c068a6d7ea8737c6dce5ac2d52e84a549ec43` |
| `28.zip` | Emuchievements | 2.0.5 | `98dcb443e81b9f9011cfe77c69eb659869c8e2df2df8b0a443df66cbfc2f5a89` |
| `52.zip` | Game Theme Music | 1.7.1-1 | `9ce293ab4db212c03c6b96dfbc5e4d92e874d33387463f53223773921f75a80e` |
| `79.zip` | Decky Notifications | 1.0.1 | `3b22dc337209615f91da566ceb968793dc163b2e509de8535fb5d0fc55817312` |
| `93.zip` | Deck Settings | 1.2.6 | `23c2a933a6883e2622f0184c33a76ce4a4e88c0a7dcd730f9bab71b8c3702132` |
| `104.zip` | Game Sync | 1.0.4 | `65e021ebb37d2ebfbfbe3dbc8af95aef9556cf484730362c6b26c4ecc3e62ccd` |
| `132.zip` | SuggestMe | 1.5.3 | `248294b5d6b9d5a5d635ce35f4b5185ce59d4e4fd59353e24df4b29d74c2ade4` |
| `118.zip` | Speed Test | 1.0.2 | `8b1ee429aece9330b83ea3fc2e7e27d007ac61a737169f20bda3f1a19ab95508` |
| `60.zip` | DeckyFileServer | 1.2.0 | `7dc2ecdcd05aa415d1ac90afaff28ecb17f77809a2bc7a77aee8e92505b976f0` |
| `125.zip` | Decky Localsend | 0.4.5 | `e271ccb55eb23f918b99a69f79aec905df4c9b2ef7b23bbf4ec1c2d1a6f0c6b7` |
| `114.zip` | Network Sentinel | 1.0.4 | `d3e07f40a0c800e72d15594e03c8c61e9bf3092524a578a0260520e735b971a5` |
| `131.zip` | Download All | 1.1.0 | `0641231eec139e3231e7b5369d0dbacefd686b52e3f2fffb39384876881408da` |
| `67.zip` | Battery Tracker | 0.2.0 | `91c388d3c1b52079314045b79671ad55c767510658b6193f6936ed6cad383b94` |
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
[Games Prefix Manager](https://github.com/Saad-Alareqi/GamesPrefixManager),
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

Speed Test's exact frontend can be replayed with `scripts/framey-audit-browser.py
--speed-test-mock` and its pinned ZIP. This opt-in mode replaces only the
Cloudflare trace/download/upload fetches with bounded in-memory responses.
The page CSP still denies external connections. Local Chromium completed an
automatic test and a Retest click; the displayed speeds are fixture artifacts,
not a measurement of internet access or worn VR usability. See
[the evidence](../../../docs/evidence/framey-speedtest-mock-2026-10-29.md).

Simple Timer also runs through actual published Decky 3.3.0 discovery, instance
RPC and events in the native isolated runtime gate. Cancel/replace/completion and
active/canceled/expired backend restarts are regression checks; the unmodified
archive must reproduce its historical lifecycle errors. Only private silent
timers/settings are used. The upstream BSD license stays unchanged.

Pause Games runs through actual published Decky 3.3.0 discovery and instance RPC
for private settings and a synthetic exclusion list. No process-control method
is called. The official frontend's standalone Toggle component separately
checks saved true/false state and matching settings callbacks; effects are inert.
RadiYo! runs through actual published Decky 3.3.0 legacy RPC in a network-isolated
container. The managed copy passes loopback station fetch, custom-station fetch
and redirect, and rejects a self-signed loopback HTTPS endpoint from both
methods. The certificate and private key under `tests/decky-runtime/fixtures`
are public test fixtures; they grant no trusted access. External radio, trusted
HTTPS and audio playback remain unverified.
SuggestMe runs through actual published Decky 3.3.0 instance RPC in the same
isolation. Its managed copy keeps certificate verification on when certifi
context creation fails. The probe covers default and empty-library reads plus
a private filter preset after restart. It uses no account credentials, external
network, actual Steam library or real Frame.
Decky Notifications runs through actual published Decky 3.3.0 legacy RPC in
network and device isolation. Its managed copy uses Decky's captured logs and
omits the upstream environment dump on certificate failure. A private certificate,
empty device list, synthetic notification read/clear and restart pass. No phone
pairing, LAN delivery, real Frame or VR notification was tested.
The opt-in `--decky-notifications-fixture` browser audit also renders one
synthetic trusted device and notification in the exact panel while blocking
all backend writes and network. See
[`framey-notifications-panel-fixture-2026-10-29.md`](../../../docs/evidence/framey-notifications-panel-fixture-2026-10-29.md).
Storage Cleaner runs through the published Decky loader with only disposable
cache markers: size/list, selected-app delete and whole-directory delete pass.
The managed copy rejects traversal and symlink delete paths. No real game or
Steam cache is deleted.
Games Prefix Manager runs through published Decky 3.3.0 legacy discovery and
RPC in the same network/device-isolated containers. Its managed copy removes
the root flag, selects the actual user's home and modern Steam library paths,
and checks prefix paths before deletion. Synthetic backups are independently
read back; repeat backups preserve earlier copies. Prefix symlinks, a replaced
compatdata symlink, traversal and backups containing symlinks are refused.
The managed panel reports refusals instead of silently refreshing. Only
private disposable prefixes are changed. See
[the scoped evidence](../../../docs/evidence/framey-prefix-manager-2026-10-29.md).
Game Sync runs through actual published Decky 3.3.0 instance RPC in the same
isolation. Only default configuration and a private setting surviving restart
are checked. No rclone, cloud sync, process signal, Frame backend or VR action
is tested.
Network Sentinel runs through the same isolated native Decky gate. Its exact
archive gets plugin-local psutil and a user-service manifest; the probe checks
discovery, private settings and one monitoring-loop sample without external
network access. It does not verify real network latency or worn VR.
The opt-in `--network-sentinel-fixture` browser audit supplies bounded
synthetic read-only replies to this exact frontend. Its status, empty History
and Settings views render locally; see
[`framey-network-sentinel-panel-fixture-2026-10-29.md`](../../../docs/evidence/framey-network-sentinel-panel-fixture-2026-10-29.md).
Battery Tracker's exact archive also has a user-service adaptation. The native
Decky gate checks discovery, empty history, Frame-shaped private battery
samples and per-app power aggregation. The real Frame probe checked only the
readable Battery-type sysfs fields; the plugin itself did not run there.
The opt-in `--battery-tracker-fixture` browser audit supplies a private
legacy-RPC history sample to this exact frontend with external network blocked.
Its recent-use panel, average-power row and lookback slider render; changing
the slider sends a bounded history request. This is synthetic UI evidence,
not live Frame recording or worn VR evidence. See
[the panel evidence](../../../docs/evidence/framey-battery-panel-fixture-2026-10-29.md).
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

Decky Ludusavi 1.2.2 (store ID 103) is pinned for dependency-discovery coverage.
Only its managed `py_modules/ludusavi.py` initializes the missing-binary state
and bounds version probes. The published loader checks missing dependencies,
a slow private executable and fallback, restart, and the unchanged-original
negative case. No real Ludusavi install, backup, restore or cloud operation is
run. See [the evidence](../../../docs/evidence/framey-ludusavi-dependency-2026-10-31.md).

TabMaster 2.15.1 (`61.zip`, SHA-256 `e08333859a32b0c177b8e9a7959c5eeeafe38f946578f7f1d161c721f0e05da5`)
runs its exact unmodified backend in published Decky 3.3.0. Its native case
uses only synthetic users, tab/filter/profile/friend/tag settings and an owned
container home. It verifies disk readback, shared-tab visibility, false values,
loader restart persistence and two clean owned loader exits. It does not
exercise Steam library-tab editing, backups/restores, browser rendering,
real Frame or physical controllers. These remain separate verification gates.

`75.zip` (Reshadeck 0.2.0) was added from the digest-verified full-catalog audit cache on 2026-11-01, without changing its catalog pin. Its upstream LICENSE is retained.
`87.zip` is the existing pinned ScreenSaver 1.1.2 store archive (87), SHA-256 `5e61f20d53e244c55a0375d6299b16cdb9701c222519c7fecd726f1926091822`, copied from the previously verified full-catalog cache on 2026-11-01. No fresh live-store version claim.
`23.zip` was added on 2026-11-01 from the existing digest-verified catalog cache; no fresh store metadata is claimed.


`38.zip` is Volume Mixer 1.2.1-1, SHA-256 `11b259ad234d0e97cfef4e6a2af3f1edfb0908d5482765af56b86b0a4601c5f3`, copied from the previously verified catalog cache on 2026-11-01. This does not claim a fresh live-store version lookup. The native case uses UID 1100, private D-Bus and silent Pulse streams, without PULSE_SERVER overriding runtime discovery. It checks real stereo volume readback, an unrelated stream, restart and strict shutdown including an extra child IPC EOF. Its original-source negative must fail Pulse discovery. Bluetooth, audible output, adapted ARM64/Frame and worn/controller use are unverified.
