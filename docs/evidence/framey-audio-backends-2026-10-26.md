# Official audio plugins: local real-backend checks

Volume Mixer 1.2.1-1 (38), Volume Boost 0.0.7 (58) and Mixer 0.1.0 (144)
passed useful audio controls in local Chromium with their **unmodified official
Python backends running in actual Decky 3.3.0**. All three remain **partial**:
this run used amd64 Linux, and Frame ARM64 dependencies/audio-session mapping
are unverified. The shared headset lock was occupied; no headset reads or
changes occurred. No worn-VR result is claimed.

The private test container and browser relay were removed after verification.

The [machine-readable observations](framey-audio-backends-2026-10-26.json)
pin all three official archives and the published Decky binary digest, and
record each browser-triggered write with independent `pactl` channel readbacks.

| Plugin | Useful behavior checked | Still unverified on Frame |
| --- | --- | --- |
| Volume Mixer | Discover two playback streams; slider click and ArrowDown change only the selected stream, 100 → 50 → 45%; other stream remains 100% | ARM64 libpulse/libdbus, actual user audio session, Bluetooth playback controls |
| Volume Boost | Both-channel slider; separate right-channel change preserves left; reopen restores sync preference and actual values; exact numeric left entry; syncing disables both right controls | `pactl`, default sink, hard-coded runtime UID, physical output, boost above 100% |
| Mixer | Exact stream volume 37 → 38%, independently read back; invalid 101 and off-step 37.5 produce no write; playback filter saved, survives actual Decky restart, hides the intended stream on reopen | `pw-dump`/`wpctl`, actual Frame session, physical output, worn VR |

## Reproduced host gap

Both Volume Boost and Mixer request `SliderField.editableValue`. Framey
previously ignored that prop and rendered only a range slider. It now supplies
an accessible numeric input with the same minimum, maximum, step and disabled
state, and emits numeric `onChange` values. Empty, non-finite, out-of-range and
browser-invalid drafts do not reach a backend. No official archive was patched.
This also makes the control available to other plugins requesting that prop;
it does not establish their compatibility.

## Runtime and isolation

The disposable Debian 13 container ran PipeWire 1.4.2, WirePlumber 0.5.8 and
PulseAudio client tools 17.0. Docker used `--network none --cap-drop ALL
--security-opt no-new-privileges`, no host audio sockets and no sound devices.
Only the archive cache and test inputs were mounted, read-only. Debian 12 was
insufficient for the published Decky binary's GLIBC requirement; that initial
runtime did not start.

Private environment:

```text
XDG_RUNTIME_DIR=/tmp/framey-audio-runtime
PIPEWIRE_REMOTE=framey-audio
PULSE_SERVER=unix:/tmp/framey-audio-runtime/pulse-native
DBUS_SYSTEM_BUS_ADDRESS=unix:path=/tmp/framey-audio-runtime/bus
DBUS_SESSION_BUS_ADDRESS=unix:path=/tmp/framey-audio-runtime/bus
```

XDG config/data/state and both Decky paths were below the private test base.
Decky ran unprivileged with `CHOWN_PLUGIN_PATH=0`, `LIVE_RELOAD=0`,
`USE_CEF_CLOSE_WORKAROUND=0` and `KEEP_SYSTEMD_SERVICE=1`. A private D-Bus
session satisfied Volume Mixer's import; there was no real BlueZ service.
Its fixed `/tmp/VolumeMixer-decky.log` existed only inside the container.

The JSON includes the complete PipeWire server configuration: only a dummy
driver and null stereo sink, no hardware factories. A second PipeWire process
loaded protocol-native, client-node, adapter, metadata and protocol-pulse with
the private absolute socket. `wireplumber --profile policy` managed this server;
that installed profile contains no hardware monitors. Only private default-sink
metadata was selected. Two `paplay --raw --format=s16le --rate=48000 --channels=2
/dev/zero` clients supplied silence named `FrameySilent0` and `FrameySilent1`.
Without policy, successful volume RPCs initially left readbacks unchanged; those
fixture attempts are excluded from the passing observations.

The browser relay served actual `ui/headset.html`, vendored React 18.3.1,
`ui/framey-host.js` and the exact archived frontends in an opaque `allow-scripts`
iframe. Outer headset/installed-plugin responses were fixture-shaped. Backend
RPC used the official Decky websocket protocol inside the isolated container:
`loader/call_legacy_plugin_method` with keyword objects for 38/58 and
`loader/call_plugin_method` with positional arguments for 144. This bypassed
Steam CEF and the production SSH/CDP transport; neither is an audio verification
claim from this run.

The relay allowed discovery/settings reads, bounded volume writes only to
identified `FrameySilent` streams/the private default sink, and Mixer filters
`[]` or `["FrameySilent0"]` with boost limit 0. It denied Bluetooth commands,
`reset_volumes` and boosts. Every volume write was followed by a separate
`pactl -f json list sinks` / `list sink-inputs` read. A clean Decky shutdown and
restart retained Mixer's actual settings file and filter behavior.

Earlier full-catalog fake-Frame evidence for these exact digests covers
install/receipt/frontend/removal transport, with plugin execution stubbed.
The new evidence adds actual local backend execution; it does not turn that
older fake-Frame result into an ARM64 backend test.

## Regression checks

The required server suite passed 1,612 tests (16 skips); all 38 focused Framey
tests and both website tests passed. The 116-plugin browser audit retained
98 initializer-ready / 18 failed, with no change to any ready state. That audit
keeps backend/network actions denied. A fresh official catalog fetch confirmed
all 116 IDs, versions and digests unchanged.

## Next device check

Acquire the normal atomic `/tmp/frame-test.lock`; refuse an existing owner.
First inspect available tools/libraries and audio runtime UID. If supported,
repeat with a private ARM64 Decky user service, isolated audio socket, dummy
sink/streams and hardware discovery disabled. Check Volume Mixer's fixed log
path for collisions before loading it. Never attach the fixture to the normal
headset output/default server. Remove only test-owned services/processes/files,
read back original service/battery state and release only the matching lock.
Keep all three partial until that check passes; physical output, Bluetooth and
worn-VR controls need separate evidence.
