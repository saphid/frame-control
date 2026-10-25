# Frame Control in the headset

**Experimental, Frame OS 0.5.6.** Tools → Frame Control in VR installs a local
panel in SteamVR's dashboard. It is a way to reach Frame Control while wearing
the headset, independent of Decky's Quick Access Menu. The panel starts only
after you opt in; its server binds to `127.0.0.1` and it uses a normal user
service. No `sudo`, root filesystem change, or Steam client patch is needed.

The companion copies its bundled UI over the existing trusted SSH connection.
On the Frame, `frame-control-headset.service` runs a loopback server and one
Chromium app window on gamescope. The window receives a dedicated `STEAM_GAME`
id, so SteamVR registers `valve.steam.desktopgame.2001947813` as a dashboard
panel. **Show in SteamVR** requests that dashboard tab; the wearer can select
it again from SteamVR's dashboard. Closing the panel stops its browser and
server. The service is not enabled at boot.

The page shows battery, free home storage and SteamVR status. Its per-run UI
key is passed in the URL fragment, removed from the address bar after load,
and sent in the `X-Frame-UI` header. The key is absent from the HTTP request
line and server log. The usual host/origin and anti-framing checks still apply.

## Real Frame test, 2026-10-25

On Frame OS 0.5.6, build `20261022.6153909`, the opt-in install started the
user service, served `/headset`, read live `/api/status` from the browser, and
registered a mapped Chromium window with SteamVR under the dedicated overlay
key. The server rejected a request with the wrong UI key. A read-only status
probe reported the user service running and the overlay registered.

The unworn headset was in standby (`activity_level` 3). SteamVR reported the
new overlay as `not_visible` even after `ShowDashboard`. An OpenVR stereo
screenshot was a uniform dark frame. The documented temporary wake attempt
(`power.turnOffScreensTimeout` 5 → 3600, `--handlewakeup`, `ShowDashboard`)
still left the overlay `not_visible`; the setting was restored to 5 and the
dashboard hidden. The X window's `xwd` image was black too. These observations
prove panel creation and page/API execution, **not wearer-visible pixels or
laser/controller input**. A worn-headset check is still required before
describing the panel as visually verified.

The test then removed the managed service and app bundle. Its unit became
inactive, port 47813 closed, the SteamVR overlay disappeared, and the Frame's
battery was 100%. Steam and SteamVR were left running. The browser profile and
extensions folder were deliberately kept.

## Remove

Use **Tools → Frame Control in VR → Remove**. If the companion is unavailable,
run:

```sh
ssh frame 'systemctl --user stop frame-control-headset.service; rm -f ~/.config/systemd/user/frame-control-headset.service; systemctl --user daemon-reload; rm -rf ~/.local/share/frame-control/headset/bundle; rm -f ~/.local/share/frame-control/headset/receipt.json ~/.local/share/frame-control/headset/server.log'
```

That command removes only Frame Control's managed panel code. The Chromium
profile remains in `~/.local/share/frame-control/headset/profile` so local
extension data is not discarded. Inspect and delete that folder separately if
you no longer want it. Third-party extensions are in
`~/.local/share/frame-control/extensions` and are never removed by this tool.
