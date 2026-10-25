# OBS end-to-end validation — 25 October 2026

**Passthrough: yes.** Real room pixels behind SteamVR panels appeared in the
live `/dev/video99` mirror, the saved OBS recording, and a decoded frame at
four seconds in a production MP4. The Frame was safely woken with
`vrcmd --handlewakeup`; no camera, power or compositor settings were changed.
This establishes the checked SteamVR mirror, not every game/mode or Steam's
own clips. Treat recordings as potentially showing the room.

## Environment and provenance

- Host: lxso2, Linux x86_64. Real OBS 30.0.2 in disposable Ubuntu 24.04/Xvfb,
  using software llvmpipe rendering and the Media Source `ffmpeg_source`.
- Frame: SteamOS 0.5.6, build `20261022.6153909`, SteamVR 2.18.2, reachable
  with the existing `ssh frame` connection. Hardware use was serialized with
  coordinator mppkd9qczt through `/tmp/frame-test.lock` and a unique owner.
- Released v0.4.30 AppImage SHA-256:
  `b1335bb06130f2cce64a0dd40a8cb60a52c68effc258dc4bc35f8c40c822d5bb`.
  The long recording started through this app's actual Electron IPC, Python
  helper and SSH stream. Robustness checks then used that released runtime
  with the final changed resources and repacked `app.asar`; this was not a
  newly built AppImage. No OBS plugin or host FFmpeg is required by the app.
- Windows release ZIP SHA-256:
  `a393cc1653f14f162b4a3e56803f7fe9bea7b04904d18577b0b2d7d7c2d95b03`.
  Checked against release SHA256SUMS; bundled Python 3.12.14.

Machine-readable measurements and the manual stimulus/analysis programs are
in [obs-validation-2026-10-25/](obs-validation-2026-10-25/).
Room images and videos remain private under `/tmp/obs-aacapv3evh` on lxso2;
only their hashes are committed in `private-artifacts.json`.

## Recording, sound, sync and latency

| Check | Measured result | What it establishes |
| --- | --- | --- |
| Real OBS recording | 187.367 s; 15,784,412 bytes; H.264 1280×720 at 30 fps; 5,621 decoded video frames; AAC 48 kHz stereo | More than three minutes through the packaged Linux path |
| OBS dropped frames | 0 encoder skips; 90 render lag/stall frames, approximately 1.6% of recording frames | The software-rendered host was not lossless; this is not a hardware-rendered performance benchmark |
| Audio | 1 kHz stimulus; FFT peak 996.094 Hz at 11.719 Hz bin resolution; peak −13.207 dBFS; 0 clipped samples; measured harmonic energy −81.32 dB relative to fundamental | Non-silent, no numerical clipping or large harmonic distortion in the checked tone; no listening or real-game quality verdict |
| Baseline A/V | Audio leads video by median 426.67 ms; range 360–426.67 ms across 36 pulses | Default OBS setup needs sync checking; not suitable for a claim of automatic accurate sync |
| Live image latency | 1,431.4 ms, n=1; clock exchange RTT 3.409 ms; screenshot polling about 20–35 ms | Overlay submission to OBS source screenshot, not physical headset motion-to-photon latency |
| Production MP4 | 5.121 s; 1920×1080, 30 fps, 153 video frames; AAC stereo; request to saved result 7.435 s | A separate production recorder saved room passthrough pixels too |

The manual stimulus places an owned black/white OpenVR marker over the mirror
and plays a 200 ms, 1 kHz tone every five seconds through the Frame's default
output. `pa_simple_get_latency` estimates when the submitted samples play;
marker submission is aligned to that estimate. This measures software output,
not an externally measured loudspeaker/physical-display event. Most submission
jitter was below 0.2 ms; compositor timing and the 30 fps/10 ms analysis grids
still limit precision. FFmpeg decodes both tracks; the analysis detects marker
edges and groups AAC pre-echo onsets within 100 ms.

A separate initial +400 ms OBS Sync Offset trial left 83.33 ms of audio lead.
Changing the offset during an already active source from 0 to +367 ms did not
improve that run (366.67 ms before, 370 ms after). Do not assume a universal
offset or that a live setting change has taken effect: reopen the source and
verify another recording. Three subsequent fresh-source trials, setting the offset **before activating**
the Media Source, measured 480 ms audio lead at 0 ms, 70 ms lead at +400 ms,
and **0 ms at +480 ms** across three pulses (30 fps video and 10 ms audio
analysis resolution). This proves a setup-specific workaround, not a universal
default. See `calibration-initial.json`. Full trial measurements are retained. Zero OBS
buffering caused missing/distorted sound and was rejected. Zero mux delay
and alternate timestamp experiments did not improve latency and were not
merged. The default capture/encoding settings remain unchanged.

## Robustness and fixes

| Failure or scenario | Fix / result | Proof |
| --- | --- | --- |
| Stop during asynchronous Python discovery could still launch later | Cancel the pending generation; expose Stop while starting | Controller regression test |
| Late stderr containing an earlier ready message changed stopping back to running | Only accept ready while starting; ignore stale child events | Original released block reproduced in `race-before.json`; controller regression |
| A non-responsive SSH process defeated timeout termination | Bounded terminate/wait then kill; SSH connection/keepalive bounds | Real SSH child deliberately stopped with SIGSTOP; clear UI failure in 15.009 s including 5 s forced cleanup; both processes gone |
| Timeout with the app's stdin still open aborted Python at shutdown | Read the control descriptor directly, avoiding a blocked buffered-stdin daemon lock | Previously reproduced fatal shutdown; final real stall shows `The Frame OBS video stopped for 10 seconds`; subprocess regression holds stdin open |
| Three Start/Stop cycles | First packets 0.890 / 0.701 / 0.709 s; Stop to idle 61.7 / 52.7 / 53.0 ms | Final patched packaged runtime, ports 15101–15103, `robustness.json` |
| Restart after stall | First packet 0.691 s | Same runtime and real Frame |
| Quit while streaming | No surviving helper at 2.021 s | Same runtime; final audit found no test FFmpeg/stimulus process |
| Port 15099 occupied | App now offers a validated alternate port and matching copyable URL | OBS occupied 15099 while real packets arrived on alternate ports; UDP cannot identify or guarantee the receiver |
| OBS before/after Start; receiver restarts | Live decoding verified, including recreated sources while relay stays active; an already-open stalled receiver may need hide/show or properties OK | Documented recovery, not automatic OBS control |
| Standby/wake | Safe wake changed a blank mirror to visible room/panels | Private mirror and saved recordings |

A forced SSH stall tests the transport failure and error/cleanup behavior.
It does **not** prove real Wi-Fi loss or full headset suspend/resume. No physical
network interface was disabled and no headset reset was performed. There is
no automatic reconnect: restore connectivity and press Start. Valid blank
standby frames do not trigger a packet timeout.

## Windows and macOS

**Windows controls remain hidden.** A disposable Windows 11 VM ran the final
helper using the released app's bundled Python and a native executable SSH
fixture. It stayed alive for three seconds without a UDP receiver, then sent
1,316-byte packets when a receiver opened. Closing its control pipe returned
exit 0 with no surviving SSH child (`windows-pipe.json`; stop measured below
the VM timer's resolution in the final run). The helper hides the SSH console
and tolerates Winsock's delayed UDP receiver-unreachable error.

The real-headset Windows attempt delivered zero packets through a temporary
host SSH bridge. Native Windows OBS, direct Windows-to-Frame SSH, firewall
behavior and packaged app Start/Stop have therefore not passed end to end.
No local FFmpeg was installed; encoding belongs on the Frame. No firewall
exception, headset authorized key, or Windows scheduled task was installed.

**macOS:** no physical Mac or macOS VM was available. Python tests and the
five controller lifecycle tests run in the macOS CI matrix; these cannot
establish capture performance, audio quality, packaged launch or OBS behavior
on a physical Mac.

## Validation and remaining limits

Local suite: **1,514 Python tests passed, 16 skipped**, 46 app tests and 18
site tests passed. The latest helper additionally passed all 11 focused OBS
tests; the controller passed all five focused lifecycle tests. Cross-platform
CI results belong to the linked PR, not these host measurements.

Still unverified: perceptual listening, real-game audio routing, accurate
default A/V sync, broad latency/performance across hosts, hours-long sessions,
physical Wi-Fi drop/full suspend recovery, physical macOS and native Windows
OBS. The app/docs now explain copyable URL/format, receiver recovery, port
selection, passthrough privacy and OBS Virtual Camera's video-only limit.
The Discord guide provides the corresponding audio-sharing choices.

Cleanup completed: Steam and vrcompositor remained running, battery 98%,
no test FFmpeg/stimulus process remained, UDP ports 15099/15101/15102/15103/15105
were bindable, task guest SSH config and the temporary bridge were removed,
and the owned headset lock was released. The disposable Windows VM was
stopped with its disk retained. See `cleanup.json`.
