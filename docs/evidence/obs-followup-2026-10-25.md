# OBS relay and MP4 follow-up, 25 October 2026 UTC

This check used a Linux x86-64 host (`lxso2`) and the real Frame running
SteamOS 0.5.6, build `20261022.6153909`. The host reached `ssh frame`. Before
device work, the task atomically acquired `/tmp/frame-test.lock`, wrote its
owner marker, and after cleanup removed only that marker and its lock. Battery
was 99–100%; SteamVR 2.18.2 reported `activity_level: 3` (standby). Steam and
SteamVR were left running. No passthrough session or game was started.

The production `scripts/obs-headset-source.py` relay reached its first local
UDP packet in 0.65–1.15 seconds across several runs. A 12-second wall-clock
capture of its MPEG-TS packets contained 325 H.264 frames at 1280×720,
spanning 10.83 seconds of video timestamps: 30.0 fps. All 324 adjacent frame
intervals were 33.333–33.334 ms, with none over 50 ms. The 826 captured TS
packets had zero sync-byte, transport-error-indicator, or per-PID continuity
errors. Six final TS packets arrived after the receiver's 12-second cutoff and
were not included in those counts. Static standby pixels cannot establish
whether a moving game would drop frames.

After the fix, the `--height 1080 --fps 60 --no-audio` fallback reached its
first packet in 0.597 seconds. An eight-second wall-clock capture contained
447 H.264 frames at 1920×1080 over 7.45 seconds of video timestamps: 60.0 fps.
All frame intervals were 16.666–16.667 ms, none over 25 ms, and its 756 TS
packets had zero continuity or transport-error-indicator errors. It had no
audio stream, as requested. The helper exited 0 on Stop, and the owned lock
was released.

The stream also contained 48 kHz stereo AAC. A 440 Hz synthetic tone played
through the Frame's default speaker output with real-time pacing appeared in
the capture for about 0.89 seconds; decoded audio had a -21.0 dB peak. This
proves an audio signal reached the output monitor and OBS transport. It does
not prove audible monitoring, real game audio, or audio/video sync: there was
no simultaneous visible marker to compare with the tone.

The production MP4 recording commands were run separately for six seconds,
then Stop, remux, and copy to the host completed. Stop returned after 7.27
seconds from Start, including six seconds of recording; the remote ffmpeg
exited 0. The copied 36,929-byte MP4 contained 188 H.264 frames at 1920×1080
and 30 fps (6.266 seconds), plus 281 AAC packets (5.994 seconds). One decoded
frame at two seconds had a single color, RGB `(22, 27, 53)`, across all
2,073,600 pixels. The test's remote files were removed; the host copy stayed
under `/tmp` for inspection.

The relay previously returned an error when the app deliberately closed its
control pipe, because its SSH child commonly exits 255 after termination.
The same test reproduced this (`helper_exit: 1`) on the real Frame. The follow-up
fix recognizes deliberate Stop and adds bounded startup and stall timeouts,
with fake-SSH regression tests. A new locked real-Frame check after the fix
received its first 1,316-byte UDP datagram in 0.697 seconds and returned
`helper_exit_after_stop: 0` after closing the app control pipe. The longer
transport and MP4 measurements above were taken before the code change; the
fix does not alter codecs or capture commands.

Prior [OBS 30 Media Source evidence](obs-media-source-real-2026-10-25.md)
records a real Frame stream in OBS on Linux. This follow-up measured the relay
with an FFmpeg receiver; OBS itself was not relaunched. Windows and macOS
application paths, wearer-visible image latency, real game sound, audible
playback, perceptual A/V sync, and active passthrough pixels remain unverified.
