# PC in the headset (Experimental)

**Tools → PC in the headset**, on Windows only. It's the Windows version of
[Mac in the headset](mac-in-headset.md): a window or a whole screen on your PC
becomes its own SteamVR panel in the Frame. Place it with the dashboard's Float
in World, Move and Size, point and click with the laser, scroll with the
thumbstick, and type on the PC's keyboard.

**It's experimental and not yet tried on a real Windows desktop or with a
headset.** It builds and passes its protocol tests on Windows in CI, but desktop
capture, Media Foundation encoding and laser input have never run on a real
PC. Expect it not to work yet. Reports are welcome through the
[feedback form](https://frame-control.pages.dev/feedback/).

## Turning it on

It's off by default. Until you tick **Turn on PC in the headset** on the card,
Frame Control starts no helper, loads none of the streaming libraries and lists
no windows. The choice is remembered on this computer. Turning it off ends
every stream, closes the viewers in the headset and stops the helper.

The card and its Tools link only appear in the Windows app. On macOS the card
is Mac in the headset, as before; on Linux and the iPhone app there's no card.

## How it works

The ported pieces are from [PR #38](https://github.com/saphid/frame-control/pull/38).
Frame Control owns the host helper, input, authentication, streaming protocol,
panel launcher and adaptation. It doesn't need Sunshine, OBS or any other
streaming app. GStreamer is bundled as ordinary libraries.

| | Windows |
|---|---|
| Capture | Windows.Graphics.Capture, through GStreamer's `d3d11screencapturesrc capture-api=wgc`, by window (HWND) or screen (HMONITOR) |
| Encoding | Media Foundation's H.264 encoder (`mfh264enc`), low latency, no B-frames. Whether it uses the GPU depends on the PC; **not verified** |
| Input | `SendInput`, mapped through the source's bounds, with per-monitor DPI awareness |

API choices are documented, not device-verified:
[Windows capture](https://learn.microsoft.com/en-us/windows/uwp/audio-video-camera/screen-capture),
[GStreamer WGC](https://gstreamer.freedesktop.org/documentation/d3d11/d3d11screencapturesrc.html),
[Media Foundation encoder](https://gstreamer.freedesktop.org/documentation/mediafoundation/mfh264enc.html).

It needs Windows 10 or 11 with Windows.Graphics.Capture and a Media Foundation
H.264 encoder (Windows "N" editions need the Media Feature Pack). Clicks and
keys can't reach administrator apps or the sign-in screen, which an ordinary
process can't drive. If Windows won't bring the chosen window to the front,
input is refused rather than sent to the app covering it: bring the window
forward, then Stop and Show again. Minimised or closed windows stop sending
pictures. Protected video isn't supported. Mac in the headset's "own display
per window" is Mac-only.

The pieces it shares with Mac in the headset:

- `ui/frame_macview.py` owns the SSH tunnel, reconnects, quality presets and
  panel launch. `ui/frame_pcview.py` picks the Windows helper
  (`ui/frame_pc_agent.py`, `ui/frame_pc_capture.py`, `desktop/capture.c`) and
  holds the on/off switch. `/api/macview` is the endpoint for both.
- `ui/mac-view.html` is the one viewer in the headset. Its frame header, H.264
  and JPEG payloads, reconnect handshake, clock sync, timing reports and input
  messages are unchanged.
- `desktop/controller.c` is a C port of the Mac helper's Swift rate controller,
  for the Windows helper. The Mac keeps its Swift original;
  `tests/test_pc_controller.py` checks the port against a frozen 600-state
  trace from it. Capture is gated before encoding, so encoded frames are never
  dropped, and an idle window's last picture still goes out once the link
  clears.
- Stream records use the Mac helper's JSON schema (`ui/frame_stream_stats.py`),
  so the benchmark's analysis is shared.

## Packaging

The Windows installer carries `resources/desktop/bundle`: `pc-host.dll` (our
adapter and the controller), the GStreamer plugins it uses (`coreelements`,
`videotestsrc`, `videoconvertscale`, `app`, `jpeg`, `videoparsersbad`,
`d3d11`, `mediafoundation`) and the DLLs they depend on, all from MSYS2's
UCRT64 packages. `libraries.json` records the GStreamer version, the plugins,
each copied DLL and the exact package versions; licence texts are in
`licenses/`.

The x264 encoder is **not** in the installer. It's GPL, and Windows encodes
with Media Foundation, so only CI's test builds include it
(`desktop/build.py --with-x264`). The macOS and Linux installers are unchanged.

From a source checkout on Windows, build the bundle from an MSYS2 UCRT64 shell
with the packages listed in `.github/workflows/pc-host.yml`:

```sh
python desktop/build.py              # what the installer ships
python desktop/build.py --with-x264  # for the native tests
```

A missing bundle is reported on the card; nothing is downloaded on first use.

The Linux adapter from #38 (desktop portal, PipeWire, VA-API) is in the tree,
because it shares `capture.c` and the controller, and CI still builds and tests
it. The app never offers it and the Linux installers don't include it.

## Measuring

The Mac benchmark accepts the PC host:

```sh
python scripts/macview-bench.py run --pc --scenario test --label pc-test
python scripts/macview-bench.py run --pc --scenario capture --source window:12345 --label windows-window
```

`capture` needs a window or screen id from the helper's `/windows` or
`/displays`. CPU sampling isn't available on PC hosts. See
[Mac in the headset](mac-in-headset.md) for the targets and shaping options.

## What's verified

- **Verified in CI, this PR:** on `windows-latest`, the native adapter builds
  and a real x264 synthetic stream passes the ticket, reconnect, timing and
  input-echo tests through the helper. The Windows installer builds with the
  bundle, and its bundled Python loads the bundle, starts the helper and
  confirms x264 isn't in it. Unit tests check the Windows-only, off-by-default
  gating, the card and the Tools link on macOS, Windows and Linux.
- **Verified, #38, 2026-09-28, real Frame on SteamOS BUILD_ID 20260925.6191901:**
  the PC helper (ARM64, on the Frame itself, x264 test pattern) streamed
  through a Mac SSH relay into the shared viewer: 400 frames at 39.3 fps,
  content latency p50/p95 15.1/28.6 ms, synthetic input p50 76.6 ms, at
  revision `cd20243`. The frame-rate and late-frame targets failed. This
  proves the helper and the viewer work together; it isn't Windows capture or
  a real PC link.
  [Raw result](../bench/results/2026-09-28-cd20243-pc-agent-frame-arm64-final.json),
  [earlier probe](../bench/results/2026-09-28-c5fc552-dirty-pc-agent-frame-arm64-hairpin.json).
- **Verified, #38, on a Mac:** the C controller matched all 600 states of the
  Swift controller's congestion and recovery trace.
- **Not verified:** anything on a real Windows desktop. Windows.Graphics.Capture,
  Media Foundation (hardware or software), encoder restarts when the bitrate
  changes, mixed-DPI and multi-monitor input alignment, window resize and
  minimise, non-US keyboard layouts, physical laser input, and how it performs
  in a worn headset. No numbers are claimed for these. Not tested with a
  headset from this branch.
- **Not reviewed independently.** #38 tried an independent review that never
  completed.
