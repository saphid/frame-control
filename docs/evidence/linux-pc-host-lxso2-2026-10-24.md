# Linux PC host feasibility on lxso2, 2026-10-24

**Blocked on this host's current desktop environment. No feature enabled and
no feature PR opened.** Investigation for [issue #23](https://github.com/saphid/frame-control/issues/23),
starting at `4e45648` (main after #154). This concerns flat desktop panels,
not Linux PC VR streaming.

## Decision

The smallest useful candidate is one explicitly selected **whole screen**,
captured through the ScreenCast portal's restricted PipeWire connection,
encoded locally with GStreamer/x264, and sent to the existing viewer through
the shared SSH controller. Input, individual windows and virtual displays
would remain unsupported until separately verified. This candidate was **not
implemented**: lxso2 currently cannot exercise the real capture permission path.

Development packages could unblock compilation, but would not create a desktop,
portal backend or consented screen. Synthetic encoding, an Xvfb screen grab or
using the Frame as its own host would not verify Linux PC desktop capture.
No host packages or services were changed.

## Evidence

Host: `lxso2`, Linux x86-64, kernel `6.8.0-139-generic`.

- `DISPLAY`, `WAYLAND_DISPLAY` and `XDG_SESSION_TYPE` were unset. The user bus
  was reachable at `/run/user/1000/bus`.
- `/run/user/1000/pipewire-0` and `/run/user/1000/wayland-0` did not exist.
  No processes matched Xorg, Xwayland, Xvfb, GNOME Shell, KWin Wayland, Weston,
  PipeWire, WirePlumber or xdg-desktop-portal at the process check.
- D-Bus `ListNames` returned D-Bus, systemd and anonymous connections, with no
  `org.freedesktop.portal.Desktop`. `ListActivatableNames` also had no desktop
  portal. These calls queried D-Bus itself without activating capture services.
- `dpkg-query` found no `xdg-desktop-portal*` or `pipewire*` packages.
  `libgstreamer1.0-0:amd64` was installed at `1.24.2-1ubuntu0.1`, but
  `gstreamer1.0-tools` was uninstalled. `gst-launch-1.0` and `gst-inspect-1.0`
  were absent from PATH. Xvfb was installed, but supplies no portal by itself.
- `pkg-config --modversion` failed for `gstreamer-1.0`,
  `gstreamer-app-1.0`, `gstreamer-video-1.0` and `libpipewire-0.3`.
  `gio-unix-2.0` reported `2.80.0`.
- `desktop/bundle/pc-host.so` did not exist.
  `python3 desktop/build.py --with-x264 --out /tmp/frame-linux-pc-feasibility`
  exited **1** before compilation: required GStreamer pkg-config modules were
  missing. No native build or encoder runtime success is claimed.

Reproduce the non-activating portal checks in the intended desktop user's
session, using that session's actual runtime directory and bus:

```sh
gdbus call --session --dest org.freedesktop.DBus \
  --object-path /org/freedesktop/DBus --method org.freedesktop.DBus.ListNames
gdbus call --session --dest org.freedesktop.DBus \
  --object-path /org/freedesktop/DBus --method org.freedesktop.DBus.ListActivatableNames
pkg-config --modversion gstreamer-1.0 gstreamer-app-1.0 gstreamer-video-1.0 gio-unix-2.0
```

## Existing implementation reviewed

- `ui/frame_pcview.py` selects PCView only on Windows and rejects Linux even
  when enabled. Linux installers do not carry its native bundle.
- `desktop/portal.c` creates a **RemoteDesktop** session, requests pointer and
  keyboard devices, and selects monitors and windows (`types=3`). It is not
  ScreenCast-only or screen-only. Its restricted fd/node and fresh-connection
  handling are reusable.
- `ui/frame_pc_agent.py` calls the selection a shared window or screen and
  picks VA-API when the element is present, falling back to x264. A bounded
  x264 slice needs explicit encoder policy and unsupported-input behavior;
  exposing the existing Linux path alone would not meet that scope.
- `app/main.js` starts Python with the inherited environment; it does not
  supply a compositor, portal backend or capture permission.
- `.github/workflows/pc-host.yml` installs native dependencies and tests
  synthetic x264/protocol behavior with fake capture consent/input. This does
  not establish interactive Linux desktop capture.
- Issue #23 and its six existing comments distinguish prior synthetic
  helper/viewer results from untested Linux desktop capture and consent.

## Verification and limits

`python3 -m unittest discover -s tests -p 'test_pc*.py' -v` exited **0**:
27 tests ran successfully, with one additional native-class setup skip
(`native PC libraries not built on this host`). Coverage includes the compiled
C controller trace, Python adapters, grants and default-off/Windows-only gates.
It does not prove native GStreamer capture or local-client streaming.

No fake/local native stream, consent prompt, real desktop capture, Frame viewer
run, benchmark, input or window mode was tested in this investigation. No SSH
connection to the Frame was needed; no lock was acquired and no headset install,
launch, stop or settings change was attempted. Issue #113 was left alone.
No issue comments or other public messages were sent.

## Concrete unblock and next slice

1. Supply an interactive Linux desktop, physical or VM, with a working
   ScreenCast portal/backend, PipeWire and accessible consent dialog. Installing
   the portal frontend alone is insufficient. A VM can establish software
   capture/x264 behavior while physical-host behavior remains unverified.
2. Install the native dependencies listed in `pc-host.yml` in that environment
   and build a local `--with-x264` bundle. Resolve x264 distribution
   licensing/source obligations before shipping it: the current build labels
   that option test-only and the Windows installer omits it.
3. Implement a ScreenCast-only session with monitor-only selection, no
   RemoteDesktop/device request, disabled input in protocol and viewer, hidden
   window/virtual-display modes, and explicit x264 selection. Preserve the
   default-off gate and existing Mac/Windows paths.
4. Verify consent acceptance/refusal/cancellation, Stop/reopen, connection loss
   and portal closure with a local client decoding actual captured content.
   Run the shared benchmark and record results without inferring hardware or
   physical laser behavior.
5. Only after local capture works, acquire the shared Frame lock once and
   follow [the headset procedure](../testing.md#headset-smoke-test) for a brief
   viewer test. If occupied, leave the lock alone and defer device testing.

These are prerequisites and proposed scope, not a ready feature. The Linux
host request in #23 remains open.
