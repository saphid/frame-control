# Plugin and modding research

Checked **2026-10-25**. Decision: keep the experimental, reversible Decky manager
and ship Frame Control's own sandboxed panel API as the supported way to add
local features. Both implementations already landed in the replacement job
while the original job was unavailable. This report consolidates their evidence
and the original research questions; it does not claim another loader was built.

## Can Decky run on Frame?

**Its ARM64 backend and Steam shared-context injection work on the tested build.
A usable Decky menu inside VR remains unverified.** Do not equate an active
service or a JavaScript plugin registration with a working headset interface.

| Requirement | Evidence | Consequence |
| --- | --- | --- |
| ARM64 Linux binary | Upstream [3.3.0](https://github.com/SteamDeckHomebrew/decky-loader/releases/tag/v3.3.0) has `PluginLoader-arm64`; Frame reports `aarch64` | ARM is not itself a blocker. Individual plugins may still ship x86 binaries or assume Deck hardware. |
| Steam Gamepad UI and CEF | Loopback `127.0.0.1:8080/json/list` exposes `SharedJSContext` plus distinct SteamVR pages | The shared context exists; the VR shell is a separate integration target. |
| CEF enable marker | `~/.steam/steam/.cef-enable-remote-debugging` is absent, but CEF already answers | No marker or Steam launch flag change is needed on this build. |
| User service manager | `systemctl --user show-environment` succeeds | A per-user service works without installing an upstream root service. The manager is degraded by a stale failed Decky unit, although its unit file is gone. |
| Filesystem | `/` currently mounts `rw` on Btrfs, `/home` mounts `rw` | This is an observation of this device, not a stock-image guarantee. Do not disable SteamOS read-only protection or install packages in `/usr`. |
| Homebrew folder | `~/homebrew` is absent | It is an installer convention, not a preinstalled SteamOS plugin API. Frame Control uses a separate managed directory. |
| Visible menu | Earlier tests registered Decky's tab only in shared JavaScript; SteamVR had no Decky overlay; headset was in standby | QAM visibility, controller input and a real plugin's visible result remain unverified. |

The fresh [read-only probe](evidence/plugins-2026-10-25.json) records SteamOS
`0.5.6`, `VARIANT_ID=vr`, build `20261022.6153909`. It confirms CEF, architecture,
mounts, user-service availability, and absence of a running managed or upstream
Decky installation. This retry did not install anything or restart Steam.

The replacement job's [detailed test record](decky-frame.md) reports:

- Decky 3.3.0 started as the normal `steamos` user and injected into
  `SharedJSContext`.
- Install → status → update → status → remove → status succeeded on the Frame.
  Removal left the unit, binary and port 1337 absent, while preserving user data.
- ProtonDB Badges 1.1.0 loaded as a passive plugin and appeared in Decky's
  shared-context registry. Its badge or menu was not seen inside VR.
- Injected frontend code can outlive backend removal until Steam's web helper
  restarts. An earlier helper-restart test cleared the globals; this retry did
  not repeat it.

These are prior documented results, separate from the fresh read-only probe.

## Installer and update choice

The upstream [installer at e42a3c8](https://github.com/SteamDeckHomebrew/decky-installer/blob/e42a3c828de90673959b4de26cf5c5d2c7830554/cli/install_release.sh)
escalates through sudo, creates `~/homebrew/plugins` and `services`, writes the
CEF marker and a system unit under `/etc/systemd/system`, and starts Decky as
root. Its architecture switch supports `aarch64|arm64`. Running this installer
is unnecessary for a compatibility check and grants more access than a panel
extension needs.

Frame Control's [manager](../ui/frame_decky.py) instead downloads the official
ARM64 asset, checks GitHub's published SHA-256 and the ELF machine, and writes
only under `~/.local/share/frame-control/decky` and `~/.config/systemd/user`.
It refuses an upstream system-service installation, requires active CEF before
install/update, and restores the previous binary, receipt and unit if applying
an update fails. Existing tests exercise that rollback with a failed service
start. These checks do not prove every possible OS or Steam update is safe.

The binary is downloaded on demand, not bundled. Plugin discovery lists the
managed directory and upstream `~/homebrew/plugins`; a public plugin browser
and installer remain deferred until visible Frame compatibility is established.
Decky plugins can execute backend code and are not isolated by Frame Control's
HTML extension sandbox. Root plugins are outside the per-user manager's scope.

Home-directory state is expected to survive SteamOS image updates, based on
SteamOS's layout; **an actual OS update and reboot persistence test has not been
performed**. Steam frontend changes, CEF availability, libc requirements and
plugin hardware assumptions can still break Decky. On failure, remove the user
service using [the documented removal command](decky-frame.md#opt-in-and-remove);
its removal path does not require a working CEF target. Test the sequence again
on each supported OS build before expanding support claims.

## Other paths

| Path | What it enables | Current limits and choice |
| --- | --- | --- |
| Decky plugins | Steam frontend hooks, optional Python backends | Backend and one passive plugin tested. VR UI, root-dependent plugins and native plugin binaries remain unverified. Keep experimental. |
| [CSS Loader](https://github.com/suchmememanyskill/SDH-CssLoader) / [DeckThemes](https://docs.deckthemes.com/) | Stylesheets applied to Steam UI | Relies on loader integration and matching Steam DOM/classes. Deck themes do not establish compatibility with Frame's separate VR shell. No theme was installed or visually tested. |
| User home / SteamOS homebrew | User services, user Flatpaks, files and helpers | Use owned folders and explicit uninstall. A folder named `homebrew` supplies no discovery or security boundary by itself. No rootfs changes needed for the chosen path. |
| Android / Lepton | Sideloaded apps, game-specific content and per-app settings | Frame Control already manages APKs and ADB. Lepton runs Android containers, not Steam's CEF UI; an Android mod does not add a Steam dashboard tab. No new Android mod was tested here. See [APKs](apks.md), [VR APKs](vr-apks.md), and [game mods](mods.md). |
| Frame Control extensions | Third-party HTML/CSS/JS panels with a small read-only bridge | Shipped in [#194](https://github.com/saphid/frame-control/pull/194), with a manifest, local folder, sandbox, example and [author guide](extensions.md). No Python imports, arbitrary SSH commands or write actions are exposed. |
| Frame Control's headset panel | Runs the local tools and extensions as a SteamVR panel | Shipped in [#198](https://github.com/saphid/frame-control/pull/198), expanded in [#201](https://github.com/saphid/frame-control/pull/201). Page/API execution and uninstall were tested; wearer-visible pixels and controller interaction remain unverified. See [test record](headset-app.md). |

The extension iframe has `sandbox="allow-scripts"`, an opaque origin, restrictive
CSP and a `postMessage` bridge accepting only `capabilities` and a reduced
`status` snapshot from the active frame. It is useful for local dashboards and
small tools today. It cannot replace the full Decky API. Third-party code still
needs review: an iframe may navigate itself externally, and local installation
does not establish publisher trust.

Extensions are loaded only when opened and are removed by closing their panel
and deleting their own directory. They modify no SteamOS files. The
[compatibility follow-up](https://github.com/saphid/frame-control/pull/209) adds
manifest `apiVersion` validation during discovery and asset serving, with
existing manifests defaulting to version 1. It rejects incompatible panels
even when requested through a direct asset URL.

## Licences: separate download versus bundling

Decky's [licence](https://github.com/SteamDeckHomebrew/decky-loader/blob/00cd202872b85868071b041c8f1b34e734147195/LICENSE)
is GPL version 2. Frame Control is MIT-licensed. The integration contains its
own service-management code and downloads the upstream executable as a separate
program. It does not incorporate Decky source or ship its binary in Frame
Control installers. Keep the upstream licence/source links visible to users
who opt in; installing a separate GPL program does not by itself relicense
Frame Control's independent code.

If a future release bundles or mirrors Decky binaries, the distributor must
preserve copyright/licence notices and satisfy GPLv2's corresponding-source
requirements for the exact binary, including modifications and build scripts
as applicable. A link to an evolving default branch is not a substitute for
meeting those distribution obligations. Mere aggregation and deriving or
linking a combined work are different questions; reassess the boundary if
Decky code is incorporated. Each plugin, theme and bundled dependency has its
own licence and assets to check independently. The existing
[third-party notices](../THIRD_PARTY_NOTICES.md) describe software already
distributed with Frame Control.

## Next checks

1. On a worn Frame, establish an accessible Decky menu or explicitly implement
   an adapter for the VR shell. Verify a passive plugin's visible result and
   controller navigation before enabling public plugin installation.
2. Verify the Frame Control panel and example extension visually, including
   opening, refreshing and closing with the controllers.
3. Test a normal Steam restart, reboot and SteamOS update with a disposable
   managed install; confirm removal still works with CEF unavailable. Retain
   the experimental label until those checks pass.

The release coordinator owns those ongoing headset-integration checks. This
retry leaves the headset untouched and hands over the research and compatibility
follow-up instead of running concurrent loader experiments.
