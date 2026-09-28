# Mac space: the Mac's desktop and its windows, placed in the room

Design notes, started 2026-09-28. The goal is Apple Vision Pro's Mac Virtual
Display, plus something Vision Pro can't do: pulling any Mac window out
to float on its own. Labels as in [ssh.md](ssh.md): **verified**,
**documented**, **reported**, **inferred**.

## What to match (Vision Pro's Mac Virtual Display)

Researched 2026-09-28. Sources: Apple Support
[118521](https://support.apple.com/en-us/118521) and the
[Vision Pro guide](https://support.apple.com/guide/apple-vision-pro/use-mac-virtual-display-tan357ede966/visionos);
[9to5Mac](https://9to5mac.com/2024/01/30/heres-what-its-like-using-vision-pro-as-an-external-mac-display/),
[UploadVR](https://www.uploadvr.com/visionos-2-2-ultrawide-mac-virtual-display/)
and [AppleInsider](https://appleinsider.com/inside/apple-vision-pro/tips/how-to-use-mac-virtual-display-for-apple-vision-pro-with-desktop-macs-and-macbooks).

- **Connecting.** Look at the Mac and a **Connect** button floats above it.
  There's also a Control Center route. The Mac's own screen goes dark
  (**documented**/**reported**).
- **Placement.** The display appears where you were looking, near the Mac,
  at a large-monitor size. After that it stays put in the room: moving the
  laptop doesn't move it. Holding the Digital Crown recenters everything
  (**documented**).
- **Handling.**
  - A **window bar** under the display moves it, with pinch and drag, and
    also moves it nearer or farther.
  - Its bottom **corners** resize it.
  - **Close** sits to the left of the bar (**documented**).
- **Modes.** Standard (16:9), Wide (21:9) and Ultrawide (32:9, about 10K
  pixels across). All are curved since visionOS 2.2 (**documented**).
- **Input.**
  - The Mac's keyboard and trackpad drive it.
  - The pointer moves to whichever window you look at (Universal Control).
  - Mac audio plays in the headset (**documented**).
- **What it can't do.** You can't pull a single Mac window out of the
  virtual display (**reported**, several sources). That's our
  differentiator.

## What the Frame allows

- **Moving SteamVR's panels from our own process: no** (**verified**
  2026-09-28). `FindOverlay("valve.steam.desktopgame.<id>")` works from a
  separate OpenVR app, but `SetOverlayTransformAbsolute` returns 12
  (`VROverlayError_PermissionDenied`). The panel reported transform type 5
  (dashboard tab). Only SteamVR's dashboard, which runs in `vrwebhelper`,
  moves them, through its privileged `VRHTML.VROverlay`, and it has no
  DevTools port. See `/tmp/fmv-space/ovprobe.py` for the probe, which stays
  outside the repo.
- **WebXR in Chromium XR: yes** (**verified** 2026-09-26/27,
  [webxr-chromium.md](webxr-chromium.md)).
  - `immersive-vr` runs at 72–75 fps.
  - Passthrough shows wherever the page leaves pixels transparent.
  - Controllers are `tracked-pointer`s with `xr-standard` gamepads, and
    squeeze events arrive.
  - Hands are tracked with 25 joints.
- **Our own OpenVR overlays: possible, but most work.** We would own their
  transforms and get laser input as mouse events for free. But the Frame
  would need native H.264 decoding and texture upload.

## Decision: a WebXR "Mac space" page first

The WebXR page (`ui/mac-space.html`) holds everything, with passthrough
behind it:

- **The desktop.** A large curved panel shows the Mac's main display,
  placed above the laptop. The first time, you place it yourself; after
  that it's remembered in the room.
- **Windows.** Each separated window gets its own panel.
- **Grabbing.** A bar under each panel moves it (squeeze, or pinch with a
  hand). Its corners resize it, and there's a close button to the bar's
  left, as on Vision Pro.
- **Pulling a window out.** Grab a window's title bar on the desktop panel
  and drag it off the edge. The page starts a `separate:<window id>`
  stream, the window moves to its own display on the Mac, and its new
  panel follows your hand until you let go. Dropping a panel back onto the
  desktop panel stops the stream, and the window goes back.
- **Input.** The laser and trigger click and drag, the thumbstick scrolls,
  and the Mac's keyboard types, as today.

Trade-offs:

- It's the headset's active app while you use it. Other VR apps pause, but
  SteamVR's own overlays still draw on top.
- Text sharpness depends on how the page renders. WebXR quad layers (the
  `layers` feature) would let SteamVR's compositor sample each panel
  directly, so they're worth checking first.

## Building blocks

- **One module for the protocol.** `ui/mac-stream.js` holds the stream
  protocol (connect, clock sync, decoding, acks and reports, input), shared
  by `mac-view.html` (the 2D panel) and `mac-space.html`.
- **A space key from the agent.** Frame Control gets a ticket with
  `src=space`, and the page trades it once for a **space key**, kept in
  memory. That key lists the windows and displays (with their positions,
  for picking the one under the pointer) and opens streams for any of
  them. Stop All revokes it.
- **Anchoring.**
  - v1: manual placement, remembered in the room (to be checked: whether
    `local-floor` stays put between sessions on the Frame).
  - v2: the Mac shows a marker on its screen for a moment, and the headset
    finds it. That needs camera access, which is **unknown** on the Frame:
    the passthrough cameras are monochrome, and `IVRTrackedCamera` hasn't
    been tried.

## Open questions

- Frame rate with several software-decoded streams at once.
- Whether `local-floor` placements survive restarts.
- Whether WebXR quad layers work in Chromium XR's OpenXR path.
- Whether Chromium grants `requestSession` without a click in the page
  (needed for a one-click "Open Mac space").
