# Decky Loader on Steam Frame

For the modding-path survey, licence review and update limits, see
[plugin and modding research](plugins-research.md).

**Status, 2026-10-25:** Decky Loader 3.3.0's ARM64 backend starts on Frame OS
0.5.6 and injects into Steam's shared CEF context. Its Decky tab registers in
JavaScript. A usable plugin menu in the Frame's VR shell has **not** been
verified. Frame Control therefore labels its user-service manager experimental.
ProtonDB Badges loaded in the backend and Gamepad UI plugin registry, but its
VR user interface has not been seen or used.

## Official store plugin audit, 2026-10-25

On a real Frame with Frame OS 0.5.6 build `20261022.6153909`, SteamVR 2.18.2
reported `activity_level` 3 (standby). The battery was 99% before and after.
The test downloaded the official store's current archives, checked each SHA-256
against store metadata, and inspected their manifests and binaries. For seven
non-root candidates, the removable user-service loader started each plugin in
turn. It stopped between plugins. Logs showed `Loaded <name>` for all seven.
The service and test folders were removed after the run; the owned shared lock
was released. **A load message is not proof that a plugin's page, settings, or
action works in VR.** No plugin was tried by a wearer.

| Official store plugin (tested version) | Result | Evidence and limit |
| --- | --- | --- |
| ProtonDB Badges 1.3.4 | Partial | ARM64 backend loaded. Earlier 1.1.0 also registered in the shared Gamepad UI; badges in the VR shell were not seen. |
| CSS Loader 2.1.3 | Partial | Backend loaded; one `SyntaxWarning`. Theme controls and CSS application in VR were not checked. |
| SteamGridDB 1.8.1 | Partial | Backend loaded. Artwork selection and its UI were not checked. |
| Animation Changer 1.3.2 | Partial | Backend loaded. Boot animation replacement was not attempted. |
| Storage Cleaner 1.4.0 | Partial | Backend loaded. No files were cleaned; no UI check. |
| HLTB for Deck 2.0.12 | Partial | Passive plugin loaded. Game page content in VR was not checked. |
| Bluetooth 3.1.1 | Partial | Backend logged `Bluetooth plugin loaded`. Pairing and VR controls were not checked. |
| PowerTools 2.0.3 | Not applicable | Manifest asks for root; archive includes x86_64 Ryzen binaries and targets Steam Deck hardware. The Frame user service blocks it. |
| Audio Loader 1.6.1 | Not applicable | Manifest asks for `_root`; the Frame user service blocks it. |
| Wine Cellar 0.2.1 | Broken on ARM64 | Archive includes an x86_64 backend binary. The store installer blocks it before execution. |
| MagicPods 2.0.21 | Broken on ARM64 | Archive includes an x86_64 `magicpodscore` binary. The store installer blocks it before execution. |
| Decky Recorder | Not in current official store | No matching plugin appeared in the official store list on this date; no archive was installed. Frame Control's own headset panel has a separate recorder. |

The table reflects the tested versions only. Other releases can change their
files or behavior. The official store's digest checks the archive in transit;
it does not certify plugin code. Plugins run with the headset user's access.
For a new plugin, follow the [Frame plugin and extension guide](frame-plugin-author.md).

The new store transaction was also exercised on the same real Frame:
**managed loader install → ProtonDB Badges 1.3.4 store install → status →
store update → store remove → managed loader remove**. Status reported the
managed store ID and version while the plugin was installed. The service
remained active after each store change. The battery was 99% before and after.
The test removed its plugin folder, loader, and owned lock. This validates the
store file and service path over SSH, not a visible VR plugin page.

Frame Control's desktop app and opt-in headset panel now show official store
entries. Install, update, and remove need an explicit confirmation. They only
change Frame Control owned plugin folders under
`~/.local/share/frame-control/decky/plugins`. The installer checks the store
hash and archive paths, blocks root plugins and non-ARM64 binaries, and rolls
back an update if the service restart fails. The current VR shell does not
provide Decky's Steam Deck Quick Access Menu. Frame Control's headset panel
shows installed plugins and store actions. Its separate Framey iframe now hosts
compatible API v2 plugin pages, settings, local routes, and panel toasts.
Steam route patches and system notifications remain unavailable. The panel
still needs a worn-headset visual and controller check. See the
[current compatibility table](frame-plugin-author.md#framey-api-v2-compatibility).

## What was checked on the real headset

The headset was SteamOS `0.5.6`, `VARIANT_ID=vr`, build `20261022.6153909`,
`aarch64` (SteamOS 3.9.x family). SSH reached it through the existing `frame`
alias. `/` was mounted read-write as Btrfs; no root filesystem change was
needed. `systemctl --user` was running. The Steam client launched with
`-cef-enable-debugging`, `-vrgamepadui`, and `-steamdeck`; its web helper served
CEF remote debugging on `127.0.0.1:8080`. The usual
`.cef-enable-remote-debugging` marker was absent, yet debugging was active.

CEF listed a `SharedJSContext` target at `steamloopback.host/routes/library/home`
and a separate `SteamVR` target for the VR overlay. The Decky 3.3.0 ARM64
binary started from `/tmp` as the normal user: port `127.0.0.1:1337` answered
HTTP 200, the log reported `Loading Decky frontend!`, and CEF showed
`window.deckyHasLoaded === true` and one registered Decky tab in
`SharedJSContext`. The `SteamVR` target had neither that global nor a Decky tab;
its current body text did not contain Decky. The Steam web helper had
`--disable-quick-menu`. This is evidence of backend and shared-context
injection, not proof of an accessible Decky plugin menu inside VR. A QAM
interaction in the headset and a plugin UI test remain necessary.

Frame Control's per-user manager was then exercised on the real Frame:
**install → status → update → status → remove → status**. The service became
active, the binary matched Decky's published SHA-256, and removal left no
service, binary or listening port 1337. Decky's already injected JavaScript
remained in Steam's running web helper until that helper was restarted. After a
web helper restart, both `deckyHasLoaded` and the tab hook were absent. All
temporary trial files and the test's empty managed data folder were removed.

## ProtonDB Badges compatibility test

The [ProtonDB Badges v1.1.0 release](https://github.com/OMGDuke/protondb-decky/releases/tag/v1.1.0)
was tested on the same Frame OS build. It is a popular, passive Decky plugin
(133 GitHub stars at test time) that adds badges to game pages. The published
archive SHA-256 was
`b4c72ff0ffe60b1a14abafe75a62f644cbb6689f398a753a1905c281151d9173`.
Its six archive entries had no links or path traversal, and its manifest declared
`flags: []` and `api_version: 2`. The release contains a frontend bundle and
no backend `main.py`; its source backend only manages its own settings.

The test copied the archive into Frame Control's managed Decky plugin folder,
then installed the official Decky 3.3.0 ARM64 binary as a user service. Decky's
log said `Plugin ProtonDB Badges is passive` and `Loaded ProtonDB Badges`.
`DeckyPluginLoader.plugins` in Steam's `SharedJSContext` contained
`ProtonDB Badges`; `deckyHasLoaded` was true there. The separate `SteamVR`
CEF target had no Decky globals or plugin text, and SteamVR listed no Decky
overlay. The headset was in standby, so no in-headset plugin page or badge
interaction was verified. The backend's unauthenticated root URL returned
HTTP 403, as expected.

The test removed the managed Decky service and binary, the test plugin folder,
and its shared-device lock. The service was no longer running, the plugin list
was empty, the binary and unit were gone, and port 1337 was closed. Decky's
already injected frontend may remain in the running Steam web helper until
Steam normally restarts; the test did not restart Steam or SteamVR.

## Why the official Decky installer is not used

The current [Decky installer](https://github.com/SteamDeckHomebrew/decky-installer/blob/e42a3c828de90673959b4de26cf5c5d2c7830554/cli/install_release.sh)
selects `PluginLoader-arm64` on `aarch64`, creates `~/homebrew/plugins`, writes
the CEF marker, installs `/etc/systemd/system/plugin_loader.service`, and uses
`sudo systemctl` to enable a **root** service. Its
[uninstaller](https://github.com/SteamDeckHomebrew/decky-installer/blob/e42a3c828de90673959b4de26cf5c5d2c7830554/cli/uninstall.sh)
also uses sudo. These scripts do not call `steamos-readonly`, but they do write
under `/etc`; their root service has broad control over the headset. The
current [Decky loader](https://github.com/SteamDeckHomebrew/decky-loader/blob/00cd202872b85868071b041c8f1b34e734147195/backend/decky_loader/injector.py)
targets Steam's shared Gamepad UI CEF page, injects a frontend served on port
1337, and patches the standard Quick Access Menu. On Frame, Steam supplies
the CEF target, while visible VR shell integration is unresolved.

Frame Control downloads only Decky's official latest ARM64 release, requires
its published SHA-256 digest, and checks the ELF architecture. It installs a
**user** service named `frame-control-decky.service` in
`~/.config/systemd/user`, with the binary and plugin folder under
`~/.local/share/frame-control/decky`. It never asks for a sudo password, edits
`/etc`, or changes CEF flags. Decky warns that running without root is not
officially supported. Plugins that require root, assume `~/homebrew`, or rely
on Steam Deck hardware may fail even if the loader runs. Frame Control lists
plugins already present in its managed folder and the upstream `~/homebrew`
folder. The opt-in store manager installs compatible archives only into its
own folder. It cannot make Steam Deck QAM plugin pages visible in Frame VR.
The experimental [Framey panel host](framey-loader.md) can render compatible
plugin settings inside Frame Control's separate SteamVR dashboard panel.
The real headset still needs a worn-user visibility and controller check.

The latest tested release was
[Decky 3.3.0](https://github.com/SteamDeckHomebrew/decky-loader/releases/tag/v3.3.0),
`PluginLoader-arm64` SHA-256
`8ef5dcf36cbbbb6e97201a6baed5d79c4cc44ec27789fc9af1c5b6ae8f0b25b6`.
This digest comes from that release's GitHub API asset metadata; it detects a
download mismatch, but is not an independent signature.

## Opt in and remove

In Frame Control, open **Tools → Decky Loader on Frame**, read the experimental
notice, check the acknowledgement box, and choose **Install**. **Update**
downloads and verifies the latest ARM64 release again. **Remove managed
Decky** disables and removes only Frame Control's user service and binary.
It preserves plugin files and settings so unrelated user data is not deleted.
Open **Official plugin store** to review a plugin, then confirm each install,
update, or remove. Root and x86-only plugins are blocked. The manager only
removes plugin folders that it installed; it leaves other Decky folders alone.
Restart Steam or the headset to clear the frontend already injected into its
current web helper process. No action wipes the headset.

Manual removal if Frame Control is unavailable:

```sh
ssh frame 'systemctl --user disable --now frame-control-decky.service; rm -f ~/.config/systemd/user/frame-control-decky.service ~/.local/share/frame-control/decky/PluginLoader ~/.local/share/frame-control/decky/.frame-control/receipt.json; systemctl --user daemon-reload; systemctl --user reset-failed frame-control-decky.service'
```

That command intentionally keeps `~/.local/share/frame-control/decky/plugins`
and `settings`. Check those folders before deleting them yourself. An upstream
Decky installation is separate; use its own installer to remove it. Frame
Control refuses to install alongside an upstream system service.

## Next compatibility test

In the headset, open Steam's VR dashboard and look for Decky's plugin tab or
Quick Access Menu after an opt-in install. If none appears, inspect whether
the VR shell exposes a different menu component and whether Decky's frontend
can target it without patching Steam globally. Confirm the plugin's visible
UI, controller interaction, and persistence across a normal Steam restart.
Until those checks pass,
Frame Control should not describe Decky plugins as usable in VR yet. A worn
headset check is needed for both the Decky menu and the Frame Control SteamVR
panel; only then can their controller interaction and plugin presentation be
confirmed.
