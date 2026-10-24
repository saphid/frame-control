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
