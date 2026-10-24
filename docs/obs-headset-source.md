# Headset view in OBS

Frame Control can send SteamVR's headset mirror and the Frame's output audio to
OBS on a Linux or macOS computer. The helper uses the same `/dev/video99` video
source and default-output monitor as **Capture & Live → Record**. It sends a
local MPEG-TS stream; no port is opened to the LAN or internet.

1. Connect to the Frame and start SteamVR. OBS runs on the computer; the Frame
   already has `ffmpeg`.
2. In the **Linux or macOS Frame Control app**, open **Capture & Live** and click
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

Ctrl+C stops the checkout helper. The app's Start/Stop control currently supports
Linux and macOS; Windows users can run the checkout helper with Python 3 and
OpenSSH from a terminal, but this path has not been verified on a Windows PC.

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
receiver. **Verified 2026-10-24:** against a real Frame running SteamOS 0.5.6,
build 20261022.6153909, the receiver saved a 4.021-second MPEG-TS sample on
the Linux PC; `ffprobe` found H.264 video and AAC audio. The temporary sample
was removed. The headset was unworn, so visible content and audible sound were
not checked. OBS itself was not installed on that PC; its Media Source setup,
monitoring and sync are still unverified.
