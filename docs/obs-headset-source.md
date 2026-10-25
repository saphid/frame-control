# Headset view in OBS

Frame Control can send SteamVR's headset mirror and the Frame's output audio to
OBS on a Windows, Linux or macOS computer. The helper uses the same `/dev/video99` video
source and default-output monitor as **Capture & Live → Record**. It sends a
local MPEG-TS stream; no port is opened to the LAN or internet.

1. Connect to the Frame and start SteamVR. OBS runs on the computer; the Frame
   already has `ffmpeg`.
2. In the **Frame Control desktop app**, open **Capture & Live** and click
   **Start OBS source**. Keep Frame Control open; **Stop OBS source**, switching
   headsets, or quitting the app closes its SSH stream. It uses the selected
   headset and the app's bundled helper.
3. In OBS, add a **Media Source**, clear **Local File**, set **Input** to
   `udp://127.0.0.1:15099`, and set **Input Format** to `mpegts`. The source
   carries video and AAC audio. Use OBS's audio mixer to choose monitoring and
   recording levels.

From a source checkout, you can instead install `python3` on the computer and
run:

   ```sh
   python3 scripts/obs-headset-source.py
   ```

Ctrl+C stops the checkout helper. The app closes a control pipe when you click
Stop or quit; the helper then closes its SSH child, including on Windows. On
Windows, install Python 3 and OpenSSH Client if Frame Control cannot find them.
The Windows app Start/Stop path still needs a physical Windows/Frame test.
If no first packet arrives within 20 seconds, or an active stream sends no
packet for 10 seconds, the helper closes SSH and shows an error instead of
leaving **Start OBS source** waiting or a frozen source running indefinitely.

To share the OBS view in a call, see the short
[Discord setup guide](streaming-to-discord.md).

`--height 1080 --fps 60` increases quality and Frame CPU use. The default is
720p30. `--port 15100` selects another loopback port; use the same port in
OBS. If the Frame's PulseAudio monitor cannot be read, the helper exits with
an error. Use `--no-audio` only when a silent view is useful. To inspect the
stream without OBS, run `ffprobe -v error -show_streams
udp://127.0.0.1:15099` in a second terminal while the helper is running.

This is the composited, undistorted one-eye **SteamVR mirror**, not a raw
passthrough camera feed. The mirror may be blank when the headset is idle or
unworn. Whether active passthrough pixels appear in it is still unverified.
The helper does not send a microphone. It is designed for one local OBS
receiver. **Verified 2026-10-25:** the helper bundled in the Linux AppImage
sent a real Frame stream to OBS 30's Media Source. OBS recorded 37.6 seconds
with H.264 video and AAC audio; a brief 440 Hz tone played to the Frame's
default output was present in the saved audio. The headset was in standby, so
the video showed the standby mirror. Nobody listened to OBS's monitoring output,
and audio/video sync and active passthrough remain unverified. See the
[test evidence](evidence/obs-media-source-real-2026-10-25.md).
The [follow-up Linux/Frame transport check](evidence/obs-followup-2026-10-25.md)
measured packet continuity and a short MP4 recording on the current SteamOS
build. The headset was still in standby.

## SteamOS / Steam Machine PC host

Use **Desktop Mode** on the SteamOS PC. Download the Linux x86_64 AppImage to
your home folder. Make it executable and open it there; SteamOS has a
read-only system root, so these steps do not use `apt` or change `/usr`:

```sh
chmod +x ~/Downloads/Frame-Control-linux-x86_64.AppImage
~/Downloads/Frame-Control-linux-x86_64.AppImage
```

If AppImage mounting reports a FUSE error, try
`APPIMAGE_EXTRACT_AND_RUN=1 ~/Downloads/Frame-Control-linux-x86_64.AppImage`.
This extracts to writable temporary space and needs enough free disk space.
Set up the Frame's SSH connection in Frame Control, then use **Start OBS
source** before you add or activate OBS's Media Source. Install OBS as the
`com.obsproject.Studio` Flatpak through Discover or your normal user Flatpak
setup. In that OBS Media Source, clear **Local File**, set **Input** to
`udp://127.0.0.1:15099`, and set **Input Format** to `mpegts`. Make a short
recording and check both picture and sound before a stream. Use **Stop OBS
source** in Frame Control when done.

The OBS Flatpak's published manifest includes `--share=network`, which is
needed for its local UDP receiver. Check your installed permissions with
`flatpak info --show-permissions com.obsproject.Studio` if OBS receives no
packets. Frame Control's helper sends to loopback on this PC; it does not
require an open LAN port or an OBS plugin. The PC does not need a system
`ffmpeg` package for the helper; encoding runs on the Frame.

**Test limit:** The v0.4.27 AppImage launched on an Ubuntu 24.04 x86_64 host
under Xvfb. Its helper sent H.264 and AAC from a real Frame to a local UDP
receiver on that host. No SteamOS 3.9.5 PC, Steam Machine, Flatpak OBS runtime,
read-only-root host, or physical display was available for this check. The
SteamOS steps and Flatpak receiver therefore remain **untested on SteamOS**.
See the [test record](evidence/obs-steamos-host-2026-10-25.md).

## Known issue: game audio in OBS

A Frame owner [reported](https://x.com/AzizahStellazio/status/2114147449468293171)
that OBS **Game Capture / Application Audio Capture** can lose game audio when
the headset turns on. OBS support attributed this to Valve/SteamVR. Frame
Control cannot change that game-audio routing. If it happens, use Frame
Control's **Start OBS source** and OBS **Media Source** steps above to capture
the headset view and its output audio. You can also try OBS **Desktop Audio
Capture** for the computer's output, then check its meter and a short test
recording before you stream. Do not leave two active sources for the same audio
unless you want duplicate sound.

The real Frame/OBS check above proved that a synthetic tone from the Frame's
output reached the Media Source recording. It did **not** use a running game,
listen to the audio, reproduce the reported Game Capture failure, or measure
audio/video sync. Real game audio while the headset is awake remains unverified.
