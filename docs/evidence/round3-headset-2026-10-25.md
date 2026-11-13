# Round 3 headset checks, 25 October 2026

These checks used the real Frame after the device hold ended. SteamOS was
0.5.6, build `20261022.6153909`. Each device session acquired
`/tmp/frame-test.lock` atomically and released only its own lock. The battery
read 100% and Full in the first check and after the OBS session; Steam and
SteamVR were left running.

| Question | Observation | Conclusion |
|---|---|---|
| Does active passthrough appear in SteamVR's `/dev/video99` mirror? | The mirror service was active. One 1920×1080 RGB frame read from `/dev/video99` had a single pixel value, `(24, 28, 53)`, throughout. The headset was unworn; no active passthrough session or wearer-visible room view was established. Frame Control has no verified remote passthrough toggle. The temporary frame was removed. | **Still unknown.** A uniform standby frame cannot answer whether SteamVR composites active passthrough into its mirror. No headset setting was changed. |
| Can Frame Control prompt when a headset text box opens? | No desktop `plasmashell` process was running during this check. There is no verified cross-app focus event from SteamVR, Lepton and the nested desktop; KDE Connect's `keyboardstate` packet describes keyboard support, not a focused text field. | **Not built.** A prompt triggered by an unverified signal would be misleading. The existing **Type on the headset** control remains available. |
| Does reverse clipboard exist? | Frame Control already has **Copy the headset's clipboard here**. Its earlier real Frame test used a temporary nested desktop and confirmed that text copied through Klipper reached a Linux PC clipboard. No desktop panel was open during this session, so it was not rerun here. | **Shipped and previously verified**, text only. Windows/macOS backends and arbitrary headset apps remain unverified on a real Frame. |
| Is an 80% charge limit available and writable? | `steamosctl get-max-charge-level` returned `UnknownInterface: ...BatteryChargeLimit1`. No `charge_control_*` attribute was found under `/sys/class/power_supply`. Only `pm8550b-charger/charging_pause` and `charging_enable` were present, each mode `644`, owner `root:root`. | **No supported user-writable control.** No battery attribute was written. |

The separate OBS transport check on the same build sent the mirror and the
default-output monitor to a Linux PC. A 4.021-second temporary capture had
H.264 video and AAC audio according to `ffprobe`. It was removed; OBS itself
and audible playback were not tested. See the OBS source PR and guide.
