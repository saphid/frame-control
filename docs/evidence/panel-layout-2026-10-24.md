# Saved panel layouts: feasibility recheck, 2026-10-24

Issue: [#31](https://github.com/saphid/frame-control/issues/31). Base: main
`5b47cd3`. This investigation covers spatial save/restore for existing
Steam/gamescope panels without another overlay application.

## Decision and user behavior

Keep saved layouts unavailable. The current Frame exposes some geometry,
including a standing-space coordinate transform, but this investigation did
not establish a complete dock-state snapshot or a controlled restore path for
these panels. The existing companion/headset switcher still lists panels and
requests focus; users arrange them with SteamVR's dashboard controls. No layout
file, new control, overlay application or background service is added.

This is a limit of the investigated route, not proof that every native
implementation is impossible. In particular, failure of
`GetOverlayTransformAbsolute` does **not** mean all pose readback is denied.

## Device and read-only results

SteamOS **0.5.6**, BUILD_ID **20261015.6141207**; `vrcmd --version`:
**2.18.2**. `gamescope-session.service` was active and
`plasma-workspace.target` inactive: Game Mode. gamescope used the OpenVR backend
and `--virtual-connector-strategy PerAppId`. Battery was 99%, Not charging,
before the probe and 100%, Full, afterwards.

The [exact probe](panel-layout-2026-10-24/probe.py) loads only
`FnTable:IVROverlay_028` from the shipped
`/opt/steamvr/bin/linuxarm64/libopenvr_api.so`. It uses application type 3
(`VRApplication_Background`, avoiding runtime startup) and shuts down its own
OpenVR connection in `finally`. Initialization and interface acquisition both
returned 0. It calls getters only, with no image capture or input injection.

[Raw result](panel-layout-2026-10-24/readback.json):

| Getter | `valve.steam.desktopgame.0` | `valve.steam.gamepadui.main` |
|---|---|---|
| FindOverlay | 0, Success | 0, Success |
| Rendering process | `gamescope-wl` | `gamescope-wl` |
| Width | 0; 2.6700000763 m | 0; 2.6670000553 m |
| Curvature | 0; 0 | 0; 0 |
| Transform type | 0; 5, DashboardTab | 0; 5, DashboardTab |
| Absolute transform | 18, WrongTransformType | 18, WrongTransformType |
| Tracked-device-relative transform | 18, WrongTransformType | 18, WrongTransformType |
| Coordinate transform, center, standing origin | 0; identity matrix | 0; scaled/translated matrix |
| Coordinate transform, center, seated origin | 23, RequestFailed | 23, RequestFailed |
| Coordinate transform, center, raw origin | 23, RequestFailed | 23, RequestFailed |

The dashboard and both panels were reported hidden; neither panel was active.
The standing-space matrix is the transform for the overlay point `(0.5, 0.5)`;
it does not identify World/Dashboard/Theater/controller docking or recreate a
dashboard frame. The Steam panel's basis has scale about 0.369. Treat neither
that scaled matrix nor the hidden Gamescope panel's identity as a validated
physical placement to feed to an absolute-transform setter. Visible placement,
matrix freshness and correspondence to dashboard size were not checked by a
wearer.

## API and dashboard boundary

The ABI and result names were checked against Valve's
[OpenVR v2.12.14 C header](https://github.com/ValveSoftware/openvr/blob/v2.12.14/headers/openvr_capi.h)
and [C++ interface comments](https://github.com/ValveSoftware/openvr/blob/v2.12.14/headers/openvr.h).
That header declares `IVROverlay_028`; its SHA-256 is
`d58a2b149e434b2b8ee25cb4253ca6157feed8092f621e78ecfed6846d35d3e4`.
The absolute getter is explicitly limited to absolute transforms. The
coordinate getter returns the 3D transform for a 2D overlay point. Public
`IVROverlay_028` has no getter/setter pair for dashboard dock location or frame
scene-graph state. The probe fails closed if that exact interface is absent.

Read-only inspection of the shipped dashboard
`/opt/steamvr/resources/webinterface/dashboard/chunk~8012d0c89.js`
(SHA-256 `937ec62c67a481f030a416099ceb98b0fe2a702aea5a0705601c6c40d4969f6d`)
found:

- `dockLocation` reads an internal `_getDockLocation(frameID)` store;
  `SetDockLocation` updates that store or sends a VRLink request.
- `m_mapLastRelativeTransformForDockLocation` keeps per-location transforms.
  World initialization requests a dashboard scene-graph transform through
  `requestSGTransform`, then updates the component's `xfTransform`.
- The `vrcmd_dock_overlay` handler accepts `dashboard`, `lefthand`, `righthand`,
  `theater` and `world`. It selects the frame associated with the supplied key,
  **falls back to the active frame if no match exists**, sets dock location and
  may switch frame. This is not an exact pose restore or a readback response.

Those are observations of shipped internal code, not proof that Frame Control
can safely access its state through a supported external API. No dashboard
JavaScript was injected, private store edited or VRLink command sent. The
active-frame fallback is an additional reason not to experiment with docking
commands on a stale key.

The [2026-09-28 probe](../panels.md#saved-spatial-layouts-blocked-on-the-current-panel-route)
on SteamOS 0.4.1 / SteamVR 2.18.1 recorded an absolute setter returning
12 (`PermissionDenied`) on a temporary, test-owned gamescope panel. That setter
result is **historical**, not a new test on 2.18.2. The newer read-only results
above neither overturn nor reverify it.

## Commands, safety and cleanup

Read-only inspection used `ssh frame` with `BatchMode=yes` and
`ConnectTimeout=10`, `cat /etc/os-release`, battery sysfs reads,
`systemctl --user is-active gamescope-session.service plasma-workspace.target`,
process inspection, and `vrcmd --version`, `--help`, `--overlays`. An initial
`--listoverlays` attempt returned `Unknown command`; `--overlays` is the actual
enumeration command. Dashboard sources were read/copied to local `/tmp` for
inspection. No files were installed on the Frame.

Run the retained probe from the repository root, following
[the shared-device rules](../testing.md#headset-smoke-test). Stop if the lock is
occupied or battery is at/below 20%; never remove another task's lock:

```sh
ssh -o BatchMode=yes -o ConnectTimeout=10 frame \
  'set -eu; mkdir /tmp/frame-test.lock || exit 3; trap "rmdir /tmp/frame-test.lock" EXIT; timeout 25 python3 -' \
  < docs/evidence/panel-layout-2026-10-24/probe.py
```

This command acquired the lock, completed with exit 0 and released it. A
subsequent check confirmed the lock absent, Game Mode active, and Steam,
`vrserver` and `vrcompositor` running. The probe's only headset filesystem
change was creating/removing that shared lock. Its Python source ran from
stdin. There were no test panels, installs, profiles or services to remove.

No mutation test was essential: without verified dock/relative-frame readback,
there was no exact original layout and bounded rollback to justify changing a
panel. Existing user panels were never focused, shown, hidden, resized, moved
or docked. No global settings, security, passwords, runtime processes or modes
were changed; no reboot or reset occurred.

## Validation and remaining gaps

Existing `tests/test_panels.py` covers main-panel enumeration, hidden panels,
focus revalidation, unavailable-runtime errors and HTTP authentication/Host/
Origin guards. `tests/test_page_scripts.py` checks the production page's shared
JavaScript scope. These offline checks do not prove spatial placement. The
retained probe is evidence tooling, not a new product API; no fake layout
backend or layout tests claiming device support were added.

Validation passed:

```sh
python3 -m unittest discover -s tests -p test_panels.py -v       # 8 passed
python3 -m unittest discover -s tests -p test_page_scripts.py -v # 5 passed
python3 -m py_compile docs/evidence/panel-layout-2026-10-24/probe.py
python3 -m json.tool docs/evidence/panel-layout-2026-10-24/readback.json
git diff --check
```

The initial panel-suite attempt hit sandbox socket restrictions in four HTTP
tests; rerunning with loopback sockets permitted passed all eight. No real
headset connection is used by those tests. The full suite and fake Frame were
not run for this evidence-only change.

Before shipping layouts, a native route still needs proof of dock state and
relative-frame readback, authorized restore on an owned test panel with exact
rollback, and correspondence between saved size/pose and visible placement.
It also needs stable source identity and a fresh capture-permission/ticket
flow when reopening viewers. Reconnect, panel recreation, reboot recovery,
Steam-launched gameplay, controller docking and worn-headset input were not
tested here. The existing Frame Control-owned media renderer is not proof that
Steam/gamescope panels can be restored. No third-party overlay app was used.

## Announcement

We rechecked saved panel layouts on SteamOS 0.5.6. SteamVR exposes some panel
geometry, but we have not verified safe restoration of Steam's panel positions
and docking. Saved layouts remain unavailable; use SteamVR's dashboard to
arrange panels. The panel switcher continues to list and show open panels.
