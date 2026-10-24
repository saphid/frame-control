# OBS Media Source on a real Frame, 2026-10-25 AEDT

The Linux x86_64 AppImage from PR #174's exact head `69fff152` had SHA-256
`4902ac80b77fbf98ec918db29df9cf9260b8abd6763a5b5055572335869f038a`.
Its extracted resources passed `app/build/check-resources.js`, including the
OBS helper, and the app launched under Xvfb with an isolated profile and a
dummy SSH alias. Its bundled server served the page with HTTP 200.

For the device test, the PC was lxso2. The real Frame was reached as `ssh frame`
under an atomically acquired `/tmp/frame-test.lock`. Battery read 100% Full
before and after. SteamVR 2.18.2 reported `activity_level: 3` (standby). The
mirror service and `/dev/video99` were active. The test cleaned its temporary
remote WAV and released only its own lock.

OBS 30.0.2 ran in a disposable Ubuntu 24.04 container on lxso2, with Xvfb and
host loopback networking. A Media Source opened `udp://127.0.0.1:15099` with
input format `mpegts`. A synthetic pattern and tone first verified the OBS
scene: its saved 43.733-second MKV had H.264 video and AAC audio with a
`-17.9 dB` audio peak. The real Frame test then ran the helper from the
extracted AppImage resources **before** OBS opened the source, so OBS joined
an ongoing stream. OBS's saved 37.600-second MKV had H.264 video and AAC audio.
The standby mirror appeared in decoded frames by five seconds. A 440 Hz tone
played briefly to the Frame's default PulseAudio output appeared in the OBS
audio recording at seconds 20–21; decoded audio peaked at `-34.4 dB`. A
separate direct recording of `@DEFAULT_MONITOR@` during the same type of tone
peaked at `-34.5 dB`. These measurements verify non-silent headset output
audio passed through the helper and OBS into the saved recording.

The first OBS attempt opened its Media Source well before the Frame sent
packets. Its output had a silent AAC track until the mirror appeared late.
Starting the helper before OBS fixed this in the second run. The setup guide
now recommends starting the source in Frame Control before adding or activating
the OBS Media Source.

The exact-head AppImage was then launched on an isolated Xvfb display and
profile with the real `frame` alias. In **Tools → Capture & Live**, clicking
**Start OBS source** changed the UI to **Stop OBS source** and showed
`udp://127.0.0.1:15099` after the first stream packet. The packaged Python
helper was running with `--frame frame`. Clicking **Stop OBS source** returned
the UI to **Start OBS source**; the helper and its remote `/dev/video99` ffmpeg
process were gone. The app exited through **File → Quit**. Battery again read
100% Full, and the owned lock was released.

**Limits:** Nobody listened to OBS audio monitoring or the Frame speakers.
Audio/video sync was not measured. The headset was unworn and in standby, so
this test does not answer whether active passthrough pixels appear in the
mirror. The OBS MKVs were temporary local test artifacts and are not included
in the repository.
