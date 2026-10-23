# Installing and buying Steam games from the Mac

Frame Control's **Get games** section lists the games you own with each one's
Steam Frame rating, installs them on the Frame, and searches the Steam store.
This page covers how it works underneath, so you can do the same from a shell.

Installed Unreal Engine games also have a **VR mod** button that installs,
starts and removes UEVR; see [VR mods](mods.md) for how it works and the
per-game table. Mod support is separate from Steam's Frame rating.

## How it works

The Frame's Steam client runs with `-cef-enable-debugging`. So its UI, a
Chromium page, answers the Chrome DevTools protocol on the Frame's loopback,
`127.0.0.1:8080`. The page titled **SharedJSContext** holds the client's own
state and API:

| Object | What it gives you |
|---|---|
| `appStore.allApps` | Every app the account owns (868 games here), with `local_per_client_data.installed`, playtime, `vr_supported`/`vr_only` and `steam_hw_compat_category_packed` |
| `downloadsStore.m_DownloadOverview` | A Map keyed by client ID. `"0"` is this machine: current app, percent, ETA, bytes/s |
| `SteamClient.Installs.*` | The install wizard: `GetInstallManagerInfo`, `ContinueInstall`, `CancelInstall`, `OpenInstallWizard` |
| `SteamClient.User.GetIPCountry()` | The store country (`AU` here), which store search needs |

`ui/frame_steam.py` is a stdlib-only WebSocket client for this page. It's piped
over SSH like the other helpers:

```sh
ssh frame 'python3 - owned'          < ui/frame_steam.py   # owned games + download
ssh frame 'python3 - install 274190' < ui/frame_steam.py   # install Broforce
ssh frame 'python3 - store 1145360'  < ui/frame_steam.py   # store page in the headset
```

The debugger port only listens on the Frame's loopback, so it's reachable over
SSH and not from the network.

## Installing a game you own

`steam steam://install/<appid>`, run over SSH, hands the URL to the running
client, which opens its install wizard. The wizard's state
(`GetInstallManagerInfo().eInstallState`) then tells you what happens next:

| State | Meaning | What `frame_steam.py` does |
|---|---|---|
| 14 complete | Steam skipped the options dialog and queued the download | Reports "queued" |
| 7 config | The options dialog is showing in the headset (library folder, compatibility note) | Calls `ContinueInstall()` when the game fits on disk, as the headset's Install button does |
| 3, 4, 6, 8, 13 | Free license, CD key, password, EULA, signup | Leaves them for you to answer in the headset |
| 15 failed | Error | Reports `errorDetail` |

**Verified 2026-09-25 (SteamOS 0.3.0, build 20260922.6101926):**

- Balatro (2379780, 67 MB) went straight to state 14 and installed in about 7 s,
  with nothing to answer in the headset.
- Broforce (274190, 0.6 GB) stopped at state 7. Calling `ContinueInstall()` over
  DevTools queued the download, and the game installed.
- Calling `SteamClient.Installs.OpenInstallWizard([appid])` directly did nothing:
  the state stayed at 0. Go through the `steam://install` URL instead.

**Inferred** from the client's JS: Steam skips the options dialog when there's
one library folder, the game fits, and there's no compatibility note to show.
Broforce is Deck "Playable", which probably explains why it stopped.

## Frame ratings

`steam_hw_compat_category_packed` holds two bits per device. The client decodes
it like this (from `steamui/chunk~2dcc5aaf7.js`):

| Device | Bits |
|---|---|
| Steam Deck | `packed & 3` |
| SteamOS | `packed >> 4 & 3` |
| Steam Machine | `packed >> 6 & 3` |
| **Steam Frame** | `packed >> 8 & 3` |

The values are 0 unknown, 1 unsupported, 2 playable and 3 verified. On
2026-09-25 this library had 12 Frame Verified, 2 Playable, 6 Unsupported and 848
Unknown games.

For games you don't own, the store's public
`saleaction/ajaxgetdeckappcompatibilityreport?nAppID=<id>` returns
`frame_resolved_category` on the same scale, along with `resolved_category`
(Deck), `steamos_resolved_category` and `machine_resolved_category`. No key or
login is needed.

## Buying

Frame Control doesn't buy anything. Purchases happen on Steam's own store page,
signed in as you:

- **Buy on Steam ↗** opens `store.steampowered.com/app/<id>/` in the Mac's
  browser (the Electron app sends `target=_blank` links there).
- **Store on Frame** runs `steam steam://store/<id>`, which opens the page in the
  Steam client on the headset. **Verified 2026-09-25:** a "Hades on Steam" page
  appeared in the DevTools page list. It wasn't visible in the headset capture
  because an app was in the foreground; it opens in Steam's dashboard.

After buying, press **Refresh** in Get games. The game shows up as owned, and
**Install on Frame** installs it.

Store search uses `store.steampowered.com/api/storesearch/?term=…&cc=…`. It
returns nothing without `cc`, so Frame Control takes the country from
`SteamClient.User.GetIPCountry()` on the Frame.

## Force quitting a running game

**Running now**, at the top of Games, lists what's running on the Frame: Steam
games, sideloaded titles, non-Steam shortcuts and Android apps. A game's library
tile, a sideloaded title's ⋯ menu and the Control Center's **Force quit a game**
card have **Force quit…** too. Each asks first ("Unsaved progress will be
lost"); from a game's own menu it checks that the game is running and says so if
it isn't. SteamVR (app 250820, and its beta 1009850) is never listed or quit:
on the Frame it shows the headset view, so quitting it isn't a way out of a game.

`ui/frame_running.py` does the work on the Frame, piped over SSH with
`frame_steam.py` as its DevTools client:

```sh
scp ui/frame_steam.py ui/frame_running.py frame:/tmp/
ssh frame 'python3 /tmp/frame_running.py list'       # {"running": [{appid, gameid, name, kind, ...}]}
ssh frame 'python3 /tmp/frame_running.py quit 620'   # {"name", "method", "message"}
```

1. **What's running.** Steam starts every game, shortcut and devkit title under
   its `reaper`, as `reaper SteamLaunch AppId=<id> -- <command>`, and the reaper
   stays the parent of the game's processes. So a running game is one of your
   own processes whose program is named `reaper`, with `SteamLaunch` and an
   `AppId=` before `--`; the game is that reaper's process tree. Steam's own list
   (`SteamUIStore.RunningApps`) and Android apps whose Lepton container is up
   (`podman ps`) are added. Names come from `appStore`, else the app manifest,
   the Android app's `meta.json` or the devkit title's folder.
2. **Steam first.** `SteamClient.Apps.TerminateApp(<game id>, false)`, the
   call Steam's own Stop makes for Android apps ([vr-apks.md](vr-apks.md)). The
   game id is the appid, or `(appid << 32) | 0x02000000` for a non-Steam
   shortcut. An Android app's container is also stopped, as the Apps tab's Stop
   does (`podman stop -t 5 lepton-steamlaunch-<instance>`).
3. **Then signals.** If the game's processes are still there after 5 seconds,
   they get SIGTERM, deepest first; whatever is left 3 seconds later gets
   SIGKILL, the reaper last, so nothing it holds is orphaned unsignalled. A pid
   is only signalled while its start time still matches, so a reused pid is safe.

Nothing is found by name. These are never signalled, even inside a game's tree:
init, the helper itself and every process above it (the SSH session), other
users' processes, and anything named `steam`, `steamwebhelper`, `gamescope`,
`gamescope-wl`, `gamescopereaper`, `gamescope-session`, `sshd`, `sshd-session`,
`ssh-agent`, `systemd`, `dbus-daemon`, `dbus-broker`, `pipewire`,
`pipewire-pulse`, `wireplumber`, `plasmashell`, `kwin_wayland`, `kwin_x11`,
`Xwayland`, `sddm`, `vrserver`, `vrcompositor`, `vrmonitor`, `vrdashboard`,
`vrwebhelper` or `vrstartup`, with everything under them.

**Not tested on a headset.** The reaper command line is how Steam launches games
on Linux desktops and the Steam Deck, **inferred** for the Frame.
`SteamUIStore.RunningApps` comes from Steam's client code as plugin loaders use
it and hasn't been seen on the Frame's build; without it, the reapers alone
decide. `TerminateApp` with a shortcut's game id is the call Steam's Stop was
seen making for an Android app (docs/vr-apks.md); for Steam games it is
**inferred**. Unit tests (`tests/test_force_quit.py`) cover the parsing, the
process selection and the escalation; the fake Frame launches its games under a
stand-in `reaper` so `tests/e2e/test_running.py` force quits a real process tree.

## Not yet checked

- Free-to-play games: `steam://install` should stop at state 3 (free license)
  for you to accept in the headset. Not tried, because it adds a license to the
  account.
- Games with a EULA (state 8).
- Installing when there's more than one library folder, such as a microSD card.
- Uninstalling. `steam://uninstall/<appid>` should open a confirmation in the
  headset.

## Optional VR software

The [VR utilities list](vr-utilities.md#optional-software) is separate from our
controls and HUD. It checks software ownership as well as games; paid utilities
are installable only when already in the loaded Frame account library. No
purchase flow is added. Public reports, local results and ownership are shown
separately, and untested tools remain untested.
