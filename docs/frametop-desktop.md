# Frametop desktops

[Frametop](https://github.com/xafnirus/frametop) runs a second, multi-screen KDE
Plasma desktop on the Frame itself: each screen is a real virtual monitor, its
own size and resolution, arranged around you in the headset. Frame Control's
**Capture & Live** page can show those screens too. A third view, **Frametop
Desktop**, lists each of them in a dropdown and captures, streams, controls and
records the one you pick.

Claims here are dated when they were checked on a real Frame; what wasn't
checked is listed at the end.

## The short version

- Frametop draws its screens with its own compositor, so Frame Control can't
  see them the way it sees gamescope's panels. It talks to the desktop's own
  KWin instead, through two interfaces KWin only opens when Frametop's **Remote
  Access** is on: `org.kde.KWin.ScreenShot2` for a screen's pixels and
  `org_kde_kwin_fake_input` for the pointer, buttons, scroll and keys.
- Turn Remote Access on and restart the Frametop desktop. Nothing is installed
  on either side: Frame Control sends `ui/frame_frametop.py` over the same SSH
  connection it already uses, and the Frame's own `python3` and `dbus` do the
  work.
- Pick a screen (`WL-0`, `WL-1`, …) and use **Capture**, **Live**, **Control**
  and **Record** as on the other two views.
- This is the `screens` backend, Frametop's default. The older `gamescope`
  backend has no nested KWin to talk to, so the view stays empty there.
- **Verified 2026-11-12** from a Linux computer against a Frame running Frame OS
  0.4.5 (build `20261022.6150929`), Frametop with two 1920×1080 screens:
  capture, live video, pointer, clicks, typing and recording all worked on the
  live desktop, with Remote Access turned on for the test.

## Turning Remote Access on

Remote Access is Frametop's own remote-desktop switch
(the
[Remote desktop over VNC](https://github.com/xafnirus/frametop/blob/main/docs/reference-features.md)
section of Frametop's docs; `desktops.sh remote info` prints the VNC address it
serves). In the Frametop tree on the Frame:

```sh
cd ~/frametop
./desktops.sh remote on
./desktops.sh restart          # the setting applies when the desktop starts
```

It is a deliberate trade: Remote Access also starts `krdpserver` for Frametop's
VNC bridge, and it runs that desktop's KWin with
`KWIN_WAYLAND_NO_PERMISSION_CHECKS=1` and
`KWIN_SCREENSHOT_NO_PERMISSION_CHECKS=1`. With those off, any program inside
the Frametop desktop could capture its screens or inject input; Frame Control
uses exactly that, and needs it. Nothing else in Frame Control changes.

When Remote Access is off the third view says so instead of showing a screen,
and says the same, in plain words, when the Frametop desktop isn't running.

## What each button does

**Capture** saves one PNG of the selected screen at its native size (1920×1080
on the test Frame), with the desktop's own cursor drawn in. A capture takes
about 36 ms on the Frame.

**Live** is H.264 video at 30 fps, 720p as the page asks for (the same
`h=720&fps=30` the other views use), encoded on the Frame and decoded with
WebCodecs in the page. Measured on the Frame: 30 frames in 0.87 s
through the whole pipeline (34.5 fps) at 1080p, about 21 KB a frame, so roughly
5 Mbit/s. The capture step itself caps at 27.9 fps with the cursor included
(35.8 ms a frame) and 40.3 fps without it.

**Control** sends taps, clicks, drags, two-finger scroll, keystrokes and typed
text to the desktop, with the same gestures as the Desktop view. The pointer is
placed where you tap, in the selected screen's own coordinates, so a click lands
on the window under it. Verified by clicking a system-tray icon (Plasma showed
its microphone OSD) and by opening krunner with Alt+Space, typing into it and
closing it with Escape.

**Record** captures the selected screen as the helper's own `.mp4` in
`~/.cache/frame-control/frametop-video` on the Frame, and when you stop it is
copied here into `~/Videos/SteamFrame` and the Frame's copy removed. Video only
— the desktop's own sound isn't captured — and up to 20 minutes, like the
other recordings.

Capture, Control and Record act on the screen selected in the dropdown; Live
restarts on the new screen when you change it.

## The screens

The dropdown lists the outputs KWin has on that desktop: `WL-0`, `WL-1` and so
on, in the order Frametop's KWin made them, with the desktop's current
resolution. Frametop adds a spare output per floating window slot
(`FLOAT_SLOTS`, 8 by default); those are hidden here, because they're working
space for floating windows, not screens you set up.

The captures are flat: each screen as its own rectangle, not the curved,
differently-placed view the wearer sees. Frametop Display Settings owns that 3D
placement, and Frame Control doesn't try to reproduce it.

## If something is wrong

- **"Frametop Remote Access is off"** — turn it on as above; the desktop has to
  be restarted for it.
- **"Frametop isn't running"** — start the desktop (`./desktops.sh start`).
- **No screens in the dropdown** — the desktop is still starting (KWin comes up
  after the session), or it uses the `gamescope` backend, which this view can't
  reach.
- **Control does nothing** — check the same things; the events go to the same
  desktop the picture comes from, so a screen that shows is a screen that takes
  input.

## How it works

The page asks the server for `/api/frametop`, which runs the helper's `status`
on the Frame: the desktop's D-Bus address, whether Remote Access is on, and each
screen's name and geometry. `status` finds the address in the environment of the
desktop's own `plasmashell` (`/proc/<pid>/environ`), because the nested KWin's
own environment isn't readable and the address changes on every restart.

A screenshot is `ScreenShot2.CaptureScreen(name, {"include-cursor": true,
"native-resolution": true}, pipe)` on that address; the helper reads the raw
BGRA frame off the pipe. Live runs the same capture in a loop, pipes the frames
into `ffmpeg -f rawvideo -pix_fmt bgra -s WxH -i - … -c:v libx264 -preset
ultrafast -tune zerolatency -x264-params aud=1:repeat-headers=1 -f h264 -`, and
the browser plays the H.264 stream through the same `/api/stream` endpoint and
WebCodecs decoder the Desktop view uses, so the first keyframe can arrive at any
time.

Control is a second helper process holding one Wayland connection to that KWin:
`org_kde_kwin_fake_input` version 5, authenticated, then absolute pointer
motion (screen position plus the tap's fraction of its size), evdev buttons
(`BTN_LEFT` and friends), scroll axes, and `keyboard_key` with Linux key codes —
the same codes the page already sends for the Desktop view. Version 5 has no
keysym request (that's version 6, newer than Frame OS 0.4.5's KWin 6.2.5), so
typed text is turned into keycodes, ASCII only.

The helper is base64-encoded into the `ssh` command line the server already
uses, so nothing is written to the Frame.

## Limits and what hasn't been checked

- Remote Access has to stay on; Frame Control doesn't turn it on for you.
- Recording is video only, and one screen at a time.
- The `gamescope` backend isn't supported (inferred: there is no nested KWin to
  talk to; the view only knows how to ask KWin).
- Not tested with one screen, with screens at different resolutions or scales,
  or with Frametop's floating windows on screen. Also not tested from a Windows
  or macOS computer, or with a VNC viewer connected to Frametop at the same
  time (that shares the desktop's cost, not Frame Control's).
