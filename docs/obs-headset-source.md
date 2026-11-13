# Headset view in OBS

Frame Control can send SteamVR's headset mirror and the Frame's output audio to
OBS on a Linux or macOS computer. A checkout helper is also available for Windows tests. The helper uses the same `/dev/video99` video
source and default-output monitor as **Capture & Live → Record**. It sends a
local MPEG-TS stream; no port is opened to the LAN or internet.

1. Connect to the Frame and start SteamVR. OBS runs on the computer; the Frame
   already has `ffmpeg`.
2. In the **Frame Control desktop app**, open **Capture & Live** and click
   **Start OBS source**. Keep Frame Control open; **Stop OBS source**, switching
   headsets, or quitting the app closes its SSH stream. It uses the selected
   headset and the app's bundled helper.
3. Expand **OBS setup** in the app to copy the Input URL and format. The port
   can be changed before Start if another program uses 15099. Use that same
   port in OBS. The sender cannot identify which program is listening.
4. In OBS, add a **Media Source**, clear **Local File**, set **Input** to
   `udp://127.0.0.1:15099`, and set **Input Format** to `mpegts`. The source
   carries video and AAC audio. Use OBS's audio mixer to choose monitoring and
   recording levels.

From a source checkout, you can instead install `python3` on the computer and
run:

   ```sh
   python3 scripts/obs-headset-source.py
   ```

Ctrl+C stops the checkout helper. The app closes a control pipe when you click
Stop or quit; the helper then closes its SSH child, including on Windows. Encoding runs on the Frame; the computer does not need FFmpeg. The desktop
app bundles Python. A source checkout needs Python 3.8+ and OpenSSH Client.
The Windows button is hidden: native Windows/Frame streaming and OBS have
not passed an end-to-end test. A Windows 11 VM passed the helper control-pipe,
late UDP receiver and child-cleanup fixture; its real-headset bridge delivered
zero packets. These are separate results, not native Windows support.
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
unworn. **Room passthrough is verified** in this mirror and the saved OBS/MP4 outputs
on SteamOS 0.5.6 after a safe SteamVR wake. Check the picture before sharing;
other games and modes may differ.
The helper does not send a microphone. It is designed for one local OBS
receiver. **Verified 2026-10-25:** the helper bundled in the Linux AppImage
sent a real Frame stream to OBS 30's Media Source. OBS recorded 37.6 seconds
with H.264 video and AAC audio; a brief 440 Hz tone played to the Frame's
default output was present in the saved audio. The headset was in standby, so
the video showed the standby mirror. That initial check did not assess listening quality, A/V sync or active
passthrough. The full validation below supersedes those gaps with measurements
and a positive passthrough result, while listening remains unverified. See the
[test evidence](evidence/obs-media-source-real-2026-10-25.md).
The [follow-up Linux/Frame transport check](evidence/obs-followup-2026-10-25.md)
measured packet continuity and a short MP4 recording on the current SteamOS
build. The newer [full OBS validation](evidence/obs-validation-2026-10-25.md)
records more than three minutes and measures audio, sync, latency and cleanup.

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

## Check sync and recover a blank source

Make a short recording of a visible click, clap or other simultaneous marker
and sound before streaming. Open **Advanced Audio Properties** in OBS. If audio
arrives early, hide/deactivate this Media Source, add a positive **Sync Offset
(ms)** in Advanced Audio Properties, then show/reactivate it, record again,
and check the result. Changing the offset during playback did not correct
the tested OBS 30 source. Setting it before activation did: a +480 ms offset
reduced a 480 ms lead to 0 ms within the test resolution in three pulses. The 2026-10-25 Linux software-rendering test measured
about 0.4 seconds of audio lead with default OBS settings. This is a measured
setup result, not a universal offset. Do not apply it blindly to another host.

Start Frame Control's source before adding or activating the OBS Media Source.
After Stop/Start or a connection failure, hide and show the Media Source, or
reopen its properties and click OK, to reopen its UDP receiver. Keep only one
receiver on a port. If another application owns 15099, stop the relay, choose
another port in **OBS setup**, and change the OBS Input to match. Sending UDP
packets does not confirm that OBS has received or decoded them.

A stalled stream ends with an error. Wake or reconnect the Frame and press
Start again; automatic reconnection is not implemented. Standby can produce
valid but blank frames, so it does not necessarily trigger a packet timeout.
A fully suspended Frame cannot be woken over an unavailable SSH connection.
