# Decky Loader on Steam Frame

**Status, 2026-10-25:** Decky Loader 3.3.0's ARM64 backend starts on Frame OS
0.5.6 and injects into Steam's shared CEF context. Its Decky tab registers in
JavaScript. A usable plugin menu in the Frame's VR shell has **not** been
verified. Frame Control therefore labels its user-service manager experimental.
ProtonDB Badges loaded in the backend and Gamepad UI plugin registry, but its
VR user interface has not been seen or used.

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
folder; it does not install plugins while their Frame UI and compatibility
are unverified.

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
