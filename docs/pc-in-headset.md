# PC in the headset (Experimental)

**Tools → PC in the headset**, on Windows only. It's the Windows version of
[Mac in the headset](mac-in-headset.md): a whole screen on your PC
becomes its own SteamVR panel in the Frame. Individual windows are available only
with streaming libraries built with Windows Graphics Capture (WGC); the shipped
MSYS2 libraries disable WGC, so this build explains that limitation and offers
whole screens. Place the panel with the dashboard's Float
in World, Move and Size, point and click with the laser, scroll with the
thumbstick, and type on the PC's keyboard.

**It's experimental.** A Windows 11 VM has captured its real desktop with
Desktop Duplication and encoded it with Media Foundation and JPEG. Physical PCs,
hardware encoding and physical laser input remain unverified. See
[the dated evidence](evidence/windows-vm-2026-10-24.md) for results and limits.
Reports are welcome through the
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
| Capture | GStreamer's `d3d11screencapturesrc`: Desktop Duplication for whole screens in the shipped build; Windows.Graphics.Capture by window (HWND) or screen (HMONITOR) when that implementation is present |
| Encoding | Media Foundation's H.264 encoder (`mfh264enc`), low latency, no B-frames. Whether it uses the GPU depends on the PC; **not verified** |
| Input | `SendInput`, mapped through the source's bounds, with per-monitor DPI awareness |

API references:
[Windows capture](https://learn.microsoft.com/en-us/windows/uwp/audio-video-camera/screen-capture),
[GStreamer WGC](https://gstreamer.freedesktop.org/documentation/d3d11/d3d11screencapturesrc.html),
[Media Foundation encoder](https://gstreamer.freedesktop.org/documentation/mediafoundation/mfh264enc.html).

It needs Windows 10 or 11 with Desktop Duplication and a Media Foundation
H.264 encoder (Windows "N" editions need the Media Feature Pack). WGC-enabled
builds can also capture individual windows. Clicks and
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

MSYS2's `gst-plugins-bad` build disables `d3d11-wgc`. The presence of
`d3d11screencapturesrc` alone does not prove WGC support: its `capture-api`,
`window-handle` and `show-border` properties are conditional. The helper queries
those properties on the instantiated element, advertises only supported
sources, and omits all three properties for the DXGI whole-screen pipeline.
It never substitutes a screen crop for an unavailable window capture.

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
- **Verified, 2026-10-24:** Windows 11 VM build 26200.8037 on lxso2, using
  the v0.4.10 installer with this fix, captured its actual desktop and streamed
  H.264 to Frame BUILD_ID `20261015.6141207`: 219 sent frame records, 215 decoded
  and drawn before the snapshot. The own-panel screenshot shows the Windows
  desktop. This short, mostly idle run does not establish performance targets.
  [Evidence, raw traces and cleanup](evidence/windows-vm-2026-10-24.md).
- **Not verified:** Windows.Graphics.Capture, physical-PC capture, hardware
  Media Foundation encoding, encoder restarts when the bitrate
  changes, mixed-DPI and multi-monitor input alignment, window resize and
  minimise, non-US keyboard layouts, physical laser input, and how it performs
  in a worn headset. No numbers are claimed for these. Not tested with a
  worn headset. See the dated VM evidence for the separate automated checks.
- **Not reviewed independently.** #38 tried an independent review that never
  completed.
