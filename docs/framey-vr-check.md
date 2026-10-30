# Checking Framey without wearing the Frame

Use the existing paired SSH alias, directly or through lxso2. Start with the
read-only check, then a temporary wake. A full input exercise is opt in:

```sh
python3 scripts/framey-vr-check.py --via lxso2 --output /tmp/framey-inspect
python3 scripts/framey-vr-check.py --via lxso2 --wake --output /tmp/framey-wake
python3 scripts/framey-vr-check.py --via lxso2 --exercise --output /tmp/framey-exercise
```

Omit `--via` when the computer can already `ssh frame`; use `--host` for another
paired alias. No SSH trust or credentials are changed. The output folder is
private by default. Stereo screenshots and the OBS mirror can contain room
pixels. Review/redact them before committing or sharing. JSON reports have
screenshot hashes and no UI access keys.

The runner acquires `/tmp/frame-test.lock` by atomic `mkdir`, writes a random
owner, then reads battery, proximity and SteamVR state. A foreign lock prevents
sensor reads, wake, installation and input. Unknown battery or below 20% aborts.
`--wake` and `--exercise` also require SteamVR activity 3 (standby); awake or
unknown activity exits before power changes, service installation or input.
Battery is read again before release. The default check never wakes or
installs anything; it returns nonzero when the panel is absent/hidden.

`--wake` saves the exact current `power.pauseCompositorOnStandby` and
`power.turnOffScreensTimeout`, sets them to `0` and `120`, calls the supported
`vrcmd --handlewakeup` and requests the Frame Control dashboard panel. It reads
OpenVR state, captures a stereo compositor screenshot through the production
`ui/frame_vrshot.py` API, and captures `/dev/video99`, the same SteamVR mirror
used by OBS. The mirror reader drains 60 frames before selecting its image,
because the first loopback buffer can contain a previous session. It restores the saved power values and reads them back. It hides
the test dashboard if the dashboard was originally closed. It does not change
the proximity sensor, tracking driver, display hardware, root filesystem,
room setup, or spatial panel placement. An unreachable suspended Frame still
needs a physical wake; an SSH command cannot reach it.

`--exercise` requires the managed headset panel and Decky services to be absent;
it refuses to replace an existing installation. It creates a random test
plugin folder, checks that its settings folder does not exist, and installs
the repository's actual sample frontend/backend, with only the plugin name
and receipt changed to distinguish this test. It installs the verified official
ARM64 Decky release through Frame Control's existing installer, followed by the
normal headset app bundle. Only the test bundle's browser startup is modified:
loopback-only `--remote-debugging-port=0` and a disposable `/tmp` browser profile.
Production browser startup is unchanged. Decky's installer can reload Steam's
web helper; this is not a Steam/SteamVR restart, but its current UI can change.
The test should run while the headset is unattended.

CDP opens the actual plugin through `openFrameyPanel`, observes the opaque
iframe through its own debugging target, and reads control geometry. OpenVR's
`IVROverlayView_003.PostOverlayEvent` supplies mouse move/down/up to the
actual gamescope overlay. The check verifies delivery to the intended element
and a trusted pointer event, toggles the sample, reads its real Decky settings
file, reopens a fresh iframe, and checks the saved value. It also clicks the
Settings/Panel tabs and quick action. The scroll diagnostic creates a temporary
160-pixel-high region with more than 700 pixels of content, moves the native
pointer over it, then attempts OpenVR smooth and discrete scroll events. It
reports region geometry, trusted pointer events, wheel events and `scrollTop`.
No wheel event or offset change means this synthetic injection path remains
unverified; it does not establish whether a physical controller can scroll.
The exercise then clicks the visible **Scroll plugin down/up** buttons through
the same native OpenVR pointer transport and requires the test region to move
down and return to the top. It also holds each button through that transport,
requires Down to move farther than a single click, and requires Up to return
to the top. These prove the synthetic button paths only; they do not identify
a physical controller or repair native wheel delivery.
Temporary controls exercise the shipped
`DFL.SliderField` and `DFL.TextField`; their values remain UI-only. Text uses
CDP `Input.insertText` after OpenVR pointer focus. This is synthetic input,
not proof of a physical controller or the SteamVR virtual keyboard.

SteamVR can leave a recreated panel hidden with a stale focus request. The
exercise waits briefly for the new overlay, then retries once by removing and
reapplying `STEAM_GAME` on its own test
browser window, then requests focus again. It never retags another application.
If the overlay stays hidden, it records a small read-only registration/service
diagnostic and stops before synthetic input. The report records whether this
recovery was needed. Registration, dashboard
visibility, actual panel visibility, and pixel capture are separate checks.
A visible docked panel can report `IsDashboardVisible=false` and
`IsActiveDashboardOverlay=false`. A zero-sized main texture or failed image
read must not be described as a texture-refresh measurement. The compositor
before/after images provide independent pixel evidence.

Normal cleanup removes only the test-created managed services and random
plugin/profile paths, restores power, cancels its power watchdog, checks battery
and settings, then releases its own lock. A four-minute independent systemd
user timer restores the saved power values even if the controlling process is
killed or disconnected. It deliberately leaves the lock and test artifacts
for recovery. `recovery.json` records the host, owner, timer, remote restore
script and original values as soon as the timer starts. The final report is
`result.json`. Cleanup errors force a nonzero exit and retain the lock; inspect
that report before manually releasing it. Never remove another job's lock.
A power watchdog is not a promise to complete service cleanup after a hard
kill. The next owner must finish that recorded cleanup first.

Exit 0 means the requested machine checks and cleanup passed. It never means
a wearer has approved readability, comfort, controller rays, haptics or text
entry on the VR keyboard. The [real-device evidence](evidence/framey-vr-2026-10-25/README.md)
records the exact tested version and limits. No public CI runner should contact
the shared headset: run this command on a paired, serialized self-hosted worker.
Ordinary CI runs `tests/test_framey_vr_check.py`, the sample backend tests, and
the same-plugin navigation regression without a headset.

## Three-minute worn checklist

1. **0:00–0:30:** Coordinate the shared lock. With an installed managed panel,
   Decky backend and harmless sample, wear the headset and open SteamVR →
   Frame Control. Check the panel is in front of you, both eyes agree, text is
   legible, and the size is comfortable. Do not use a save-cleaning plugin.
2. **0:30–1:15:** Run
   `python3 scripts/framey-worn-check.py --via lxso2 --worn-confirmed`. Within its 35-second
   interaction window, use the physical controller to open the sample and
   toggle **Example setting**. Confirm the laser aims where expected and the
   script records a fresh input/panel event and visible stereo output. The flag
   is the operator’s statement. The script requires valid locked SteamVR activity
   and proximity readings before input; proximity alone cannot establish wear.
   Sensor activity and trusted pointers can also be produced synthetically and
   cannot identify controller hardware.
   The JSON `passed` value covers only the script's machine checks.
   `wornVisualComfortVerified` and `controllerHardwareVerified` stay false;
   record the wearer's visual and physical-controller observations separately.
3. **1:15–2:15:** Use the controller to open Settings, return to Panel, invoke
   **Read saved setting**, close/reopen the plugin, and confirm the value
   remains. Try controller scroll, a slider and a harmless text field in an
   installed compatible plugin. Hold **Scroll plugin down** and then **Scroll
   plugin up** with the controller; record continuous movement separately from
   native thumbstick or wheel scrolling. Check SteamVR's actual keyboard and Back.
4. **2:15–3:00:** Restore the original sample setting. Switch away and back,
   close/reopen the Frame Control panel, and confirm controller input still
   works. Record comfort/legibility, controller model, any haptic behavior,
   keyboard behavior and the command's JSON separately. Confirm battery and
   release only your lock. Do not infer these human checks from synthetic input.

The watchdog's creation and cancellation are exercised on the real Frame.
A forced host kill/network loss followed by timer recovery has not been fault
injected. Its saved recovery script remains available on a cleanup failure.
