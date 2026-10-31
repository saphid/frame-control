<div align="center">

<img src="docs/img/icon.png" width="112" alt="Frame Control icon">

# Frame Control

**Manage your Valve Steam Frame from your computer.**<br>
See what the headset sees, install games and Android apps, move files and text across, and check battery and status, all over SSH.

[![Latest release](https://img.shields.io/github/v/release/saphid/frame-control?label=release&color=1a9fff)](https://github.com/saphid/frame-control/releases/latest)
[![Platforms](https://img.shields.io/badge/macOS%20%7C%20Windows%20%7C%20Linux-2a475e?label=runs%20on)](#install)
[![Checks](https://img.shields.io/github/actions/workflow/status/saphid/frame-control/checks.yml?branch=main&label=checks)](https://github.com/saphid/frame-control/actions/workflows/checks.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-66c0f4)](LICENSE)

[**Website**](https://frame-control.pages.dev) · [**Download**](#install) · [Trailer](#trailer) · [Features](#features) · [Set up the headset](#set-up-the-headset) · [Feedback](#feedback) · [Docs](#going-further)

<br>

<img src="docs/img/frame-control.png" alt="Frame Control's Games tab: installed games, sideloaded titles, and your Steam library with Frame ratings" width="900">

<a id="trailer"></a>
<a href="https://github.com/saphid/frame-control/releases/download/trailer/frame-control-trailer.mp4"><img src="docs/img/trailer.jpg" alt="Watch the Frame Control trailer" width="900"></a>

<sub>The trailer: 66 seconds, with sound. Downloads the MP4 from the trailer release.</sub>

<sub>Unofficial hobby project, not affiliated with Valve. Free and open source.</sub>

[See what was tested on a real Frame, in a VM, or only in automated checks](docs/current-support-matrix.md).

</div>

---

## Features

<table>
<tr>
<td width="50%" valign="top">

**👓 Headset view and Desktop**<br>
Live video of what the lenses show, or of the app panel in use, flat and still however the wearer looks around. Turn on Control and tap or click right on it to use the Frame from your phone or computer.

</td>
<td width="50%" valign="top">

**🔋 Battery and status**<br>
Charge, charging watts and time left, storage, memory, temperature, Wi-Fi, and what's running.

For PC-side USB, driver, radio and network manager evidence, use the
[Linux Wireless Adapter doctor](docs/linux-wireless-adapter-doctor.md).

For repeatable read-only battery, power-rail, temperature and fan measurements,
use the [power and heat sampler](docs/power-and-heat.md).

</td>
</tr>
<tr>
<td valign="top">

**🎮 Steam games**<br>
Everything you own with its Steam Frame rating. Install onto the headset with live progress, search the store, and force quit a game that stops responding.

</td>
<td valign="top">

**🤖 Android apps**<br>
About 4,500 F-Droid apps rated for the Frame. One click installs each as its own app in your Steam library.

</td>
</tr>
<tr>
<td valign="top">

**📁 Files and games**<br>
Drag files onto the window to send them. Drop a game's .zip, folder or .exe to add it to the Steam library, with Proton or the Linux runtime picked for you.

</td>
<td valign="top">

**📸 Screenshots and recordings**<br>
Browse the shots you take in the headset and save them to your Pictures folder, or have new ones and your Steam clips copied over automatically. Record SteamVR's mirrored headset view, with its sound, or export Steam's clips at any length, as .mp4 files in your Videos folder. [Recording details and passthrough limits](docs/recording.md#does-record-include-passthrough).

**⌨️ Keyboard and trackpad**<br>
Type and point in the headset from your computer or phone, through Valve's own input path, with nothing to install. Accents and emoji use KDE Connect, which Frame Control brings along and sets up the first time you type one. Copy text to the headset's clipboard and back again. Ctrl, Alt, Shift, Super and special keys have explicit forwarding, with a shortcut menu for keys your computer captures. Press T to open it. [Supported keys and test limits](docs/keyboard-input.md).

</td>
</tr>
<tr>
<td valign="top">

**🧩 Flatpaks and display**<br>
Install desktop apps like Moonlight or VLC, and set each Android app's resolution and text size.

</td>
<td valign="top">

**⚡ One-click tools**<br>
SSH, SFTP, Steam Link, remote desktop, volume, sleep, restart and shut down.

</td>
</tr>
<tr>
<td colspan="2" valign="top">

**💾 Backup and recovery**<br>
Copy game saves, settings and Android app data to your computer, and restore them after a factory reset. Sign-in files and keys are never copied. A Return to Game Mode button helps when the headset is stuck in Desktop Mode. Not tested on a headset yet. [How it works](docs/backup-and-recovery.md).

</td>
</tr>
</table>

The optional [Family and comfort](docs/family-comfort.md) card adds session
limits, breaks, local alerts and one-click casting. A session copies a small
Frame Control worker into your headset user account.

For the other features, nothing is installed on the Frame: the app uses what SteamOS
already ships (sideloading a game copies Valve's own devkit scripts to
`~/devkit-utils`, as Valve's Devkit Client does). The optional
[performance HUD](docs/vr-utilities.md) copies our own Python helpers into
`~/.local/share/frame-control/vr/`. [How each feature works](docs/frame-control.md).

## Install

**Install Frame Control on your computer, not on the headset.** The website is
for downloads and instructions; it does not connect to your Frame in a browser.
Choose the operating system and processor of the computer you will use.

| | Download | Needs |
|---|---|---|
| **macOS** (Apple Silicon) | [Frame-Control-mac-arm64.dmg](https://github.com/saphid/frame-control/releases/latest/download/Frame-Control-mac-arm64.dmg) | Nothing extra |
| **macOS** (Intel, v0.4.39+) | [Frame-Control-mac-x64.dmg](https://github.com/saphid/frame-control/releases/latest/download/Frame-Control-mac-x64.dmg) | Nothing extra |
| **Windows** 10 / 11 (x64) | [Frame-Control-Setup-x64.exe](https://github.com/saphid/frame-control/releases/latest/download/Frame-Control-Setup-x64.exe) · [portable .zip](https://github.com/saphid/frame-control/releases/latest/download/Frame-Control-win-x64.zip) | OpenSSH Client (normally installed) |
| **Linux** (x64) | [AppImage](https://github.com/saphid/frame-control/releases/latest/download/Frame-Control-linux-x86_64.AppImage) · [.deb](https://github.com/saphid/frame-control/releases/latest/download/Frame-Control-linux-amd64.deb) | `ssh` (most desktops have it) |
| **Linux** (arm64) | [AppImage](https://github.com/saphid/frame-control/releases/latest/download/Frame-Control-linux-arm64.AppImage) · [.deb](https://github.com/saphid/frame-control/releases/latest/download/Frame-Control-linux-arm64.deb) | `ssh`, and `adb` for Android apps (`sudo apt install adb`) |

### Is it safe? Check your download

Starting with **v0.4.26**, get the installer and [SHA256SUMS](https://github.com/saphid/frame-control/releases/latest/download/SHA256SUMS) from the **same release**. Earlier releases do not have this file. A matching SHA-256 means your file matches that release asset. It does not prove the app is free of malware. Use the command for your downloaded file, then compare all 64 characters with its line in `SHA256SUMS`:

```powershell
# Windows PowerShell
Get-FileHash .\Frame-Control-Setup-x64.exe -Algorithm SHA256
```

```sh
# macOS: shasum -a 256 Frame-Control-mac-arm64.dmg
# Linux: sha256sum Frame-Control-linux-x86_64.AppImage
```

The [source](https://github.com/saphid/frame-control) and [release build workflow](.github/workflows/release.yml) are public. The Windows installer is **not code-signed**, so SmartScreen may warn. The macOS app has only an **ad hoc signature**, not an Apple Developer ID signature; the DMG is **unsigned and not notarized**, so Gatekeeper may warn or block it. Only follow the opening steps below if you trust the download.

日本語: [5 ステップの接続ガイド](docs/connection-faq.md#日本語-5-ステップで接続)を参照してください。v0.4.26 以降は公式リリースの SHA256SUMS とファイルの SHA-256 値を照合してください。Windows は未署名、macOS は開発者 ID による署名・公証がありません。

**Which build?** On a Mac, check Apple menu → About This Mac: use `mac-arm64`
for Apple Silicon (M-series), or `mac-x64` for Intel (available from v0.4.39). On Windows,
check Settings → System → About → System type: the release is x64, not a native
Windows ARM build. On Linux, `uname -m` reports `x86_64` (x64) or `aarch64`
(arm64). Use `.deb` on Debian/Ubuntu, or AppImage on other distributions.

**iPhone and iPad:** no App Store, TestFlight or `.ipa` download is provided in
the current release. It runs from your phone without a computer after setup.
Build it from [`ios/`](ios) in Xcode on a Mac with your own signing team; see
[docs/iphone.md](docs/iphone.md).

The app brings its own Python and `adb`. macOS includes SSH; Windows needs the
OpenSSH Client optional feature (normally installed).
From 0.4 it updates itself: when a new version is published, a banner offers
**Update and restart**. It sends anonymous usage statistics, which you can turn
off. Sharing compatibility results and error details is opt-in. See
[docs/privacy.md](docs/privacy.md).
Google doesn't publish `adb` for arm64 Linux, so that build uses your
distribution's. If you already have `adb`, the app uses yours.

<details>
<summary><b>macOS: the app isn't notarized</b></summary>

The app has an **ad hoc signature**, no Apple Developer ID signature, and no
notarization. The DMG is unsigned. First verify the download against the
`SHA256SUMS` from the same release, then open the DMG and drag **Frame Control**
to **Applications**.

Check your processor before opening: v0.4.38 and earlier publish only
`mac-arm64` for Apple Silicon. On an Intel Mac, this build cannot run;
removing quarantine or installing Rosetta does not make an ARM app run on Intel.
On a real Intel MacBook Air with macOS 15.7.7, opening v0.4.35 and v0.4.36
reported: **“The application cannot be opened because it has an incorrect
executable format.”** This is an architecture failure, not an observed
Gatekeeper warning. The official **v0.4.39 Intel DMG** was then verified,
installed and launched on that Air. Both CLI and T3 browser downloads lacked
quarantine metadata; no Gatekeeper dialog appeared, while `spctl` rejected the
ad hoc signed app. This does not verify Safari/Chrome warnings or Open Anyway.
See the [released Intel test](docs/evidence/mac-v0439-2026-10-26.md) and
[earlier architecture failure](docs/evidence/mac-desktop-2026-10-26.md).

On a compatible Mac, if macOS blocks an unverified developer, try opening the
app once, then go to **System Settings → Privacy & Security → Open Anyway**
and confirm **Open**. Only do this for a download you verified and trust.
[Apple's opening instructions](https://support.apple.com/102445) describe the
current security controls. The exact warning and this override flow have not
yet been verified here on either Mac architecture.

If a trusted, verified copy still reports “damaged” and offers no Open Anyway
option, the Terminal fallback removes only this app's download quarantine
(it does not sign or notarize the app):

```sh
xattr -dr com.apple.quarantine "/Applications/Frame Control.app"
```

Then open it from Applications. Do not disable Gatekeeper globally. Depending
on the features you use, macOS may also request Local Network access, permission
to control Terminal, or Screen Recording; approve only the feature you intend
to use. Those permission prompts were not verified in the release test above.

</details>

<details>
<summary><b>Windows: SmartScreen warning</b></summary>

The installer isn't code-signed, so Windows SmartScreen may say it protected
your PC. Choose **More info → Run anyway**. The portable `.zip` avoids the
installer: unzip it anywhere and run `Frame Control.exe`.
</details>

<details>
<summary><b>Linux: running the AppImage</b></summary>

```sh
chmod +x Frame-Control-linux-*.AppImage && ./Frame-Control-linux-*.AppImage
```

If it complains about FUSE, install `libfuse2` (Ubuntu 24.04+: `libfuse2t64`),
or run it with `--appimage-extract-and-run`.
</details>

## Open the app

**Optional: open at login.** In the installed desktop app, choose **Frame → Open at Login**. It is off by default. When on, a login launch starts in the tray or menu bar if that control is available; click its icon to open the window, or use its **Quit Frame Control** menu item. Closing the window keeps the app in the tray while this option is on. Turn the same menu option off to remove its OS login item. On Linux this creates or removes only Frame Control's own file in `~/.config/autostart/` (or `$XDG_CONFIG_HOME/autostart/`). If the desktop has no working tray, the window opens at login instead. A source checkout does not offer this setting.

- **macOS:** open the `.dmg`, drag **Frame Control** to **Applications**, then
  open it from Applications. For the Gatekeeper warning, use the macOS steps
  above. Allow local network access and control of Terminal when prompted.
- **Windows:** run the installer, then open **Frame Control** from Start. For
  the portable download, extract the entire `.zip` first and run
  `Frame Control.exe` inside it. See the SmartScreen note above.
- **Linux:** install the `.deb` with your package installer and launch
  **Frame Control** from your applications menu; or make the AppImage executable
  and run it as described above. Install the OpenSSH client if `ssh` is missing.

## Set up the headset

Keep the Frame awake and connect it and your computer to the same trusted local
network. Guest Wi-Fi/client isolation can prevent discovery and connections.

1. **On the Frame:** Steam Settings → System → **Enable Developer Mode**, then
   Developer → **Set User Password**. Choose a password that isn't easy to guess:
   it also protects `sudo` and remote desktop, even after SSH keys are set up.
2. **On your computer:** open Frame Control and choose **Set Up Connection…**.
   If you dismissed the first-run prompt, use **Frame → Set Up Connection…**.
   Setup opens a terminal and tries to find the headset. If it can't, use its IP
   address from Quick Settings or Steam Settings → Internet. Windows/Linux setup
   prompts for it; macOS exits instead. On macOS, return to the app →
   **Devices & connection → + Add a headset…**, set SSH alias to `frame` for
   the default headset, fill in **Address**, then choose **Set Up…**.
3. **Pair or enter the password:** setup first tries Valve's devkit pairing.
   Open Steam Settings → Developer → **Pair new host** in the headset and approve
   only the request you just started. The service and pairing-mode step are
   verified on a Frame; approval and key installation through that flow remain
   unverified. If pairing fails or times out, setup falls back to asking for the
   Developer Mode password in the computer's terminal. Password typing may show
   no characters; press Enter when done. See [SSH details](docs/ssh.md#password-free-pairing-steamos-devkit-service).
4. After setup succeeds, return to Frame Control. It uses SSH keys for later
   connections whenever the Frame is awake and reachable. If it stays offline,
   check Developer Mode, the address and network isolation, then run setup again.
   For connections away from home, see [Tailscale](docs/tailscale.md).

**Does Frame Control lower streaming lag?** No. Frame Control manages the Frame
over SSH. SteamVR or Steam Link carries the game stream. Frame Control does not
carry that stream, lower ping, or need the Wireless Adapter. It can connect over
Wi-Fi, the Wireless Adapter, or USB when your computer has an SSH route to the
Frame. The wired doctor checks only that SSH route. A data-capable USB-A-to-C
cable has not been tested for the Frame's USB network. See the
[connection FAQ and Japanese quick start](docs/connection-faq.md).

**What it changes:** only what you click. Installs go to your user account on
the Frame (`--user` Flatpaks, Lepton instances, Steam downloads, sideloaded
games in `~/devkit-game`), and nothing
needs `sudo` except the power buttons. On your computer it adds a `Host frame`
entry to `~/.ssh/config` and keys at `~/.ssh/id_ed25519_frame` and
`~/.ssh/id_rsa_frame_devkit` (the pairing service only takes RSA keys).

## Feedback

This is a first public test, so reports are really useful, especially from
Windows and Linux. The quickest way is **Report a problem** in the app (the
speech-bubble button at the top, or **Help → Report a Problem…**). It adds
diagnostics with personal details removed, shows you exactly what's included,
and sends it privately to the maintainer; nothing is published. Without the app,
use the [feedback form](https://frame-control.pages.dev/feedback/). Please include:

- what you tried and what happened
- your computer's OS and your SteamOS build (Steam Settings → System)
- the server log: **Frame → Show Server Log** in the app

Issues and PRs opened directly on GitHub by new contributors are auto-closed
until a maintainer approves them; see [CONTRIBUTING.md](CONTRIBUTING.md).

## Going further

This repo also holds the scripts behind the app and field notes on how the
Frame's software fits together, all checked against a real headset and labelled
**verified** or **inferred**.

| | |
|---|---|
| [Frame Control in detail](docs/frame-control.md) | Every feature, how it works, per-platform notes, building |
| [Scripts and headset setup](docs/scripts.md) | The command-line helpers, minimum typing, streaming options, floating panels |
| [How the Frame works](docs/how-the-frame-works.md) | SteamVR → gamescope → Plasma, verified facts, debugging |
| [SteamOS October 2026 compatibility](docs/steamos-2026-10-compat.md) | Frame OS 0.5.6 connection changes and SteamOS 3.9.5 PC host notes |
| [Android apps (Lepton)](docs/apks.md) | Sideloading, the rated F-Droid catalogue, per-app instances |
| [Import from my Quest](docs/quest-import.md) | Copy games you own off your Quest by USB; what runs, and why licence-checked games may not |
| [My Meta library](docs/meta-library.md) | Experimental: install and test Quest games your Meta account owns, with your own token |
| [Sideloading Linux and Windows games](docs/sideloading.md) | A .zip, folder or .exe as a Steam Devkit Game, runtime detection |
| [Install links for websites](docs/web-install.md) | `frame-control://install` links and manifests, the rules, a button to paste |
| [VR comfort and HUD](docs/vr-utilities.md) · [Steam games](docs/steam-games.md) · [VR video](docs/vr-video.md) · [WebXR in Chromium](docs/webxr-chromium.md) | Installing and buying, watching VR180/360, the Chromium build |
| [Steam desktop sharing (Linux)](docs/steam-pipewire.md) | External Steam helper: launch with `-pipewire` after exiting Steam, or open KDE permissions to re-pick a screen manually; no automatic permission reset |
| [PC in the headset](docs/pc-in-headset.md) | Experimental, Windows only, off until you turn it on: a whole PC screen as a panel in the Frame. Tested in a Windows VM; individual windows need a WGC-enabled build |
| [Mac in the headset](docs/mac-in-headset.md) | Mac windows and screens as panels in the Frame, with laser and keyboard input |
| [VR mods and custom songs](docs/mods.md) | UEVR for Unreal games from Frame Control (install, play in VR, remove), the per-game table, Beat Saber blockers |
| [Decky Loader on Frame](docs/decky-frame.md) · [Frame Control in VR](docs/headset-app.md) · [Frame plugin author guide](docs/frame-plugin-author.md) · [Frame Control extensions](docs/extensions.md) | Experimental Decky support, a removable headset panel, and the local extension API |
| [SSH](docs/ssh.md) · [Streaming](docs/streaming.md) · [Files](docs/file-transfer.md) · [Panels](docs/panels.md) · [Tailscale](docs/tailscale.md) | Topic notes |
| [Frame Control for iPhone](docs/iphone.md) | The iPhone and iPad app, how it runs the server on the Frame, pairing |
| [Recovery and OS images](docs/recovery-and-images.md) | Where to download the Frame's OS, what's inside, testing without the headset |
| [AI agents and assistant](docs/agents.md) | Key-free MCP tools, human approvals, and an opt-in assistant panel |
| [Power and heat measurements](docs/power-and-heat.md) | Read-only sampling and offline HTML reports with JSON/CSV downloads |
| [Testing](docs/testing.md) | Unit tests, end-to-end tests against a fake Frame in Docker, the headset smoke test and a Windows test VM |
| [Open questions](docs/open-questions.md) | What's still unchecked |

<details>
<summary><b>Security notes</b></summary>

- With Developer Mode on, `sshd`, ADB and xrdp are all reachable on your LAN.
  Each running Lepton (Android) instance opens its own ADB port in 5555–5599,
  listening on `0.0.0.0` rather than only loopback. This was seen on the
  device on 2026-09-25, so anyone on the network can reach it. Use trusted
  networks only, and turn Developer Mode off when you don't need it.
- Frame Control reaches ADB and the Steam client's DevTools port (Frame
  loopback `127.0.0.1:8080`) only through SSH tunnels. The compatibility
  database key (maintainer-only) is never written to the repo.
- `steamos` has `sudo`, protected by the same Developer Mode password. Once
  you've switched to key auth, that password still protects `sudo` and RDP,
  so pick one that isn't trivially guessable.
- Don't port-forward 22, 3389, or 5555–5599 from your router. For remote access,
  use Tailscale: `scripts/tailscale-on-frame.sh` (no sudo). In its userspace mode
  **every** Frame port is reachable from your tailnet, including Steam's DevTools
  on loopback 8080; see [docs/tailscale.md](docs/tailscale.md).
</details>

## Development

```sh
python3 -m unittest discover -s tests   # server tests; no headset needed
scripts/e2e.sh                          # end-to-end against a fake Frame (Linux with Docker)
scripts/frame-sim.sh up                 # a fake Frame on 127.0.0.1 to try changes on (Docker)
cd app && npm install && npm start      # run the app from the checkout
```

The [Frame simulator](docs/testing.md#frame-simulator) shows up in the app's
Devices as `frame-sim`, so a change can be tried without the headset.

The server is Python stdlib only; the app is Electron. GitHub Actions runs the
tests on macOS, Windows and Linux, and a `v*` tag builds all three installers
into a draft release, which reaches users once published. See
[building](docs/frame-control.md#building) and [releasing](docs/releasing.md).

## License

[MIT](LICENSE). The apps also ship other people's software under its own
licence, notably KDE Connect (GPL) for the keyboard and trackpad; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Steam, Steam Frame and SteamVR are trademarks of Valve
Corporation. This project isn't affiliated with or endorsed by Valve.

See [Game storage](docs/game-storage.md) for read-only headset space and Steam install sizes, and [the changelog](CHANGELOG.md) for unreleased changes.
