# SteamOS PC OBS host feasibility check, 2026-10-25 UTC

The available x86_64 host, lxso2, runs Ubuntu 24.04.3. It has no `flatpak`
command, OBS installation, SteamOS 3.9.5 VM or physical Steam Machine. This
check therefore does **not** verify that Frame Control or Flatpak OBS runs on
a SteamOS desktop or a read-only-root PC host.

The downloaded v0.4.27 Linux x86_64 AppImage matched GitHub's SHA-256 digest
`42d774653c69b193c3d577743c32b8fe8dfeee7ea1f8cdf7369902962d647b83`.
With `APPIMAGE_EXTRACT_AND_RUN=1`, it launched under Xvfb using an isolated
profile and its bundled server returned HTTP 200. FUSE mounting, physical
display rendering and SteamOS-specific dependencies were not tested.

The v0.4.27 tagged OBS helper then ran against the real Frame under the shared
`/tmp/frame-test.lock`. Frame OS was 0.5.6 and SteamVR activity level was 3
(standby). A receiver bound to `127.0.0.1:15099` on lxso2 accepted 497
MPEG-TS packets, 93,436 bytes. Every datagram had complete 188-byte packets
with sync bytes. `ffprobe` found H.264 video and AAC audio. Closing the
helper's control pipe made it exit 0; no owned remote stream process remained.
Battery read 100% Full before and after, and the owned lock was released. The
temporary `.ts` file was removed. This proves the local UDP sender path on an
Ubuntu host; it does not prove Flatpak OBS could receive it on SteamOS.

The public
[OBS Flatpak manifest](https://github.com/flathub/com.obsproject.Studio/blob/master/com.obsproject.Studio.json)
lists `--share=network`, which permits use of the host network. We read that
manifest but did not install or run the Flatpak. A future check needs a real
SteamOS 3.9.5 desktop host or VM with Flatpak OBS: launch the AppImage without
root changes, start the source, record from the Media Source at
`udp://127.0.0.1:15099`, verify video and audible game audio, then stop and
confirm cleanup. The standby test cannot establish real game audio, A/V sync
or active passthrough in the mirror.
