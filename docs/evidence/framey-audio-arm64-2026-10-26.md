# Official audio plugins on the ARM64 Frame

Volume Mixer 1.2.1-1 (38) and Mixer 0.1.0 (144) now qualify as **works for
per-app volume control**. Their exact official, unmodified Python backends ran
in published Decky 3.3.0 ARM64 on Frame OS 0.5.6. Local Chromium rendered the
actual Framey panels and changed only a deliberately created silent playback
stream in the Frame's real user audio session. Independent Pulse readbacks
confirmed the changes. This is useful backend behavior, not initializer-only
or fake-backend evidence.

Volume Boost 0.0.7 (58) remains **partial**. Its real ARM64 default-sink reads
matched independent `pactl` reads, and its controls rendered. Default-sink writes
were denied throughout the real-Frame run. Its earlier slider/numeric write
checks used an isolated amd64 virtual sink.

[Digest-pinned observations and cleanup](framey-audio-arm64-2026-10-26.json)
record both runs. No physical audible output or worn-VR result is claimed.

| Plugin | Real Frame result | Remaining limits |
| --- | --- | --- |
| Volume Mixer | `pulsectl`/`ravel` import; real Pulse session discovery; silent-stream slider click 100 → 50%, ArrowDown → 45%; reopen reads back the 38% subsequently set by Mixer | Bluetooth discovery/playback commands, audible output and worn-VR input unverified. The range input rounds the reopened 0.38000488 backend value to its configured step; no extra write occurred. |
| Volume Boost | `pactl` default sink and stereo channel parsing; both backend reads return 0 and agree with independent 0% / 0% sink reads; local panel shows 0 | No real default-sink writes or boosts; no audible output or worn-VR result. Zero alone is not proof: upstream returns 0 when its command fails. |
| Mixer | `pw-dump`/`wpctl` available; real playbacks/settings reads; exact silent-stream numeric input 37%, ArrowUp → 38%, independently read back | Exposes internal Frame PipeWire nodes as well as apps. Internal-node controls and Reset were not exercised. Filter persistence passed on amd64 earlier, not ARM64. Audible output and worn-VR input unverified. |

## Runtime and transport

The normal atomic `/tmp/frame-test.lock` was acquired separately for each run.
An existing owner would abort testing; the lock was never stolen. The headset
was not woken, and no power setting was changed.

The actual Frame UID is 1000. The legacy plugins' hard-coded
`XDG_RUNTIME_DIR=/run/user/1000` therefore reaches this Frame's existing audio
session. Volume Mixer's bundled pure Python wrappers successfully loaded the
system ARM64 Pulse and D-Bus libraries. No native rebuild was needed. It also
sets `HOME=/home/deck` inside its own plugin process; this test does not establish
that arbitrary Deck paths work on the Frame.

The upstream `PluginLoader-arm64` release was verified against GitHub's
published SHA-256 and ELF machine 183 before transfer. Two private, bounded,
removable user-service installs used their own Decky plugins/settings bases.
Neither service was enabled. The normal managed Decky service was already
failed, and the normal headset-panel service inactive; both states remained
unchanged. A pre-existing `/tmp/VolumeMixer-decky.log` would have aborted the
run because the upstream plugin truncates that fixed path during import.

The local relay served actual `ui/headset.html`, vendored React, `framey-host.js`
and digest-checked official frontend bytes in an opaque `allow-scripts` iframe.
Only outer status/install responses were fixtures. Plugin RPC used production
`framey_panel.call_method`, SSH through lxso2, `frame_steam.Page`, the live Steam
CEF `DeckyBackend.call`, and actual Decky plugin subprocesses. Private install
paths were redirected to the temporary base. No second Decky websocket client
was attached. This does not verify the deployed headset HTTP endpoint or a VR
compositor interaction.

## Safe control check

The first run was read-only. Independent `pactl info`, default-sink volume and
`pw-dump` commands exited successfully, so empty/zero fallback values were not
accepted on their own. Volume Mixer saw a live Steam stream; Mixer also saw
Frame spatialization, echo-cancellation and ALSA internal nodes.

For the second run, a separate task-owned transient user service ran:

```sh
paplay --raw --format=s16le --rate=48000 --channels=2 \
  --client-name=FrameySilentARM64 \
  --stream-name='Framey ARM64 silent verification' /dev/zero
```

This sends zero-valued samples to the existing user server. It is an explicit
silent client, not the earlier private null-server fixture. No server, device,
default-route or physical-sink configuration was changed. The relay resolved
its live stream IDs before every write and allowed only this exact application
name, bounded to 80% volume. The spatialization node with a similar prefix was
excluded. All Volume Boost writes, Mixer Reset/settings writes and Bluetooth
commands were denied. Existing streams and internal nodes were never write
targets. This broader real-session check supersedes the earlier suggested
null-server-only ARM64 follow-up; that older fixture could not prove access to
the Frame's real session.

Every browser-triggered volume RPC was followed by independent
`pactl --format=json list sink-inputs` channel readback. Only the named silent
stream's rows are published. Background streams can appear/disappear naturally;
no whole-session stability claim is made.

## Cleanup and catalog interpretation

Both runs removed their private Decky units/bases and the test-created fixed
plugin log. The live run also stopped its transient silent client. Decky's main
process exited during shutdown but left children waiting; those remaining
processes were killed only within the test service's systemd cgroup before
cleanup completed. Both locks were released after cleanup. An independent
fresh-lock audit confirmed all three test units unloaded/inactive with PID 0,
private paths absent, and no named silent stream. Battery was 100 → 100 and
independent default-sink reads stayed 0% / 0% in both runs.

The canonical store data and generated compatibility table now report
**3 works / 48 partial / 54 broken / 11 N/A**. “Works” describes the tested
per-app control behavior; read each row's remaining limits. Historical
[fake-Frame archive checks](framey-module-lookup-2026-10-26.md) cover transport
with plugin execution stubbed, and the
[earlier local audio checks](framey-audio-backends-2026-10-26.md) cover isolated
amd64 controls/filter persistence. Neither is relabelled as a real ARM64 test.

## Repository checks

The full Python suite passed 1,621 tests (16 skips), and the focused Framey
suite passed all 43 tests. `scripts/framey-compatibility-doc.py --check` and
`git diff --check` passed. A fresh official-store fetch at 04:11:59 UTC found
all 116 IDs, versions and digests unchanged. This PR changes catalog/evidence
and generated documentation; it adds no backend shim or plugin patch.
