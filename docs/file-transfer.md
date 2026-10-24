# File transfer and clipboard

The confidence labels are the same as in [ssh.md](ssh.md). Everything here
depends on SSH working through the `frame` alias from `scripts/connect.sh`.

## Options

| Option | Command | Confidence | Notes |
|---|---|---|---|
| **scp / rsync over SSH** | `./scripts/push.sh file-or-dir [dest]`, or `rsync -a --progress x frame:Downloads/` | **Inferred.** SSH is confirmed. Valve recommends WinSCP (SFTP) for Windows ([debugging](https://partner.steamgames.com/doc/steamhardware/steamframe/debugging)), which means SFTP is enabled. | Recommended. The Mac ships `rsync` (newer macOS uses `openrsync`, which supports the flags used here). `rsync` must also exist on the Frame. It's in SteamOS on Deck; if it's missing on the Frame, `push.sh` falls back to `scp`. |
| SFTP GUI | Finder can't do SFTP. Use Cyberduck / Transmit / ForkLift with `sftp://steamos@frame.local` | Inferred | Good for browsing. |
| `adb push` | `adb push x /sdcard/Download/` (Lepton) | Confirmed that ADB exists ([adb_lepton](https://partner.steamgames.com/doc/steamhardware/steamframe/adb_lepton)) | Only reaches the Android container's storage. |
| SteamOS Devkit Client | "Title Upload" | Confirmed (Frame) ([loadgames](https://partner.steamgames.com/doc/steamhardware/steamframe/loadgames)) | For deploying apps and games, not general files. macOS support for the Devkit Client wasn't confirmed. |
| Syncthing | A Syncthing Flatpak on the Frame (`./scripts/install-apps.sh <flathub-app-id>`), app on the Mac | Guess (which Syncthing Flatpak, and whether it has an aarch64 build, not checked) | Good for an ongoing shared folder. |
| KDE Connect | KDE Connect on both | Guess | There's a macOS build of KDE Connect, but whether it's present or installable on the Frame wasn't confirmed. It would give you clipboard sync, file send, and remote input. Worth checking on-device. |
| microSD | Physical card | Confirmed that the slot exists ([Wikipedia](https://en.wikipedia.org/wiki/Steam_Frame)) | Offline fallback. |

Screenshots and Steam clips have their own buttons on **Tools → Capture &
Live**, and **Settings → Copy to this computer** copies new ones here
automatically: see [recording.md](recording.md#copying-new-ones-automatically).

## Clipboard

`scripts/paste-to-frame.sh` sends the Mac clipboard (or stdin) to the
headset's desktop clipboard. You can then paste in the headset with the
virtual keyboard's paste key or a right-click → Paste.

```sh
./scripts/paste-to-frame.sh                 # sends pbpaste
echo "https://example.com" | ./scripts/paste-to-frame.sh -
```

How it works (verified 2026-09-25). The headset's desktop is a Plasma Wayland
session nested inside gamescope, with its own runtime dir
(`/run/user/1000/nested_plasma`) and its own D-Bus bus. `wl-copy` and `xclip`
aren't installed. The script reads the bus address from `plasmashell`'s
environment and calls Klipper's `setClipboardContents` with `qdbus6`. The
desktop has to be running in the headset. It's text only, and pastes over about
100 KB hit the argument limit, so send big things with `push.sh`.

A simpler fallback: `ssh frame 'cat > ~/clip.txt'` < file, then open it in the
headset.

### In Frame Control

**Tools → Type on the headset** (also on Home, and press `T` anywhere) has the
clipboard next to the keyboard and trackpad, both ways:

- **Send text** or **Send this computer's clipboard** puts text on the headset's
  clipboard, as above.
- **Copy the headset's clipboard** brings it back: copy something in a desktop
  app on the Frame, then press it, and paste on your computer. It calls
  Klipper's `getClipboardContents` on the same D-Bus bus, and sends the text
  back as base64, so accents, emoji and line breaks arrive unchanged. The
  desktop app and the iPhone app put it on their own clipboard. With the server
  in a browser, the server sets the clipboard of the computer it runs on:
  `pbcopy` on macOS, PowerShell's `Set-Clipboard` (or `clip.exe`) on Windows,
  `wl-copy`, `xclip` or `xsel` on Linux.

It's text only, and copying back takes up to 1 MB; a bigger clipboard is
refused with a message, so send big things as a file. An empty clipboard, or
one holding an image, says so. Neither the server nor its log ever records what
was on the clipboard.

**Not tested on a headset yet.** Reading uses the same Klipper interface as
sending, which was verified on 2026-09-25, but `getClipboardContents` itself
hasn't been tried on a Frame. The fake Frame (`tests/fakeframe`) answers it.
