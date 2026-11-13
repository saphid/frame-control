# Silent MPRIS runtime fixture

`player.py` implements the synthetic target used by the
[Music Control runtime evidence](../../../docs/evidence/framey-mpris-runtime-2026-10-26.md).
It produces no audio. It requires system Python `dbus`, `gi` and GLib, and writes
its independent control state to `/tmp/mpris-state.json`.

Run it only in a disposable container with **no network, devices, host home,
audio or D-Bus mounts**. Create a private session bus listening at
`/run/user/<container UID>/bus`: both official backends hard-code that path.
Set `DBUS_SESSION_BUS_ADDRESS` to that private socket for the fixture. Use a
private home including `.local/share/Steam/steamui/images`, because the upstream
plugins create an album-art symlink on startup. Never run these plugins against
a real user's player during this test: ID111 probes volume automatically.

Install each pinned archive separately through the managed transaction, then
start the published Decky 3.3.0 loader with private `UNPRIVILEGED_PATH` and
`PRIVILEGED_PATH`. Do not instantiate the legacy Plugin class: invoke methods
through Decky's `loader/call_legacy_plugin_method` route with its keyword object.
The two official entries share the `MusicControl` folder, so cannot coexist.
This fixture is opt-in and is not imported by ordinary unit tests.
