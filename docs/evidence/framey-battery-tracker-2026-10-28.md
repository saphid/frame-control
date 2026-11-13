# Battery Tracker 0.2.0 user-service adaptation

Official store ID 67, ZIP SHA-256 `91c388d3c1b52079314045b79671ad55c767510658b6193f6936ed6cad383b94`; the exact `main.py` SHA-256 is `2303ec70c262f1cbfe1c8c138770c6e7c3496827e748e679c94ca43ff9f28725`. The BSD-licensed archive requests `_root`, hard-codes Steam Deck `BAT1`, raises on empty history, and drops the final sample in per-app grouping. The backend records local battery readings in plugin runtime SQLite; it does not need privileged writes for the verified path.

The digest-scoped managed install removes `_root`, discovers a readable supply whose `type` is `Battery` (preferring `BAT1` on Deck), fixes empty and single-sample history, retains pending samples while the panel is open, and flushes them on unload. The original ZIP and license remain pinned in the test fixture. Changed archive bytes still fail the root gate; other root plugins remain blocked.

Under a unique owner token on `/tmp/frame-test.lock`, a **read-only** real Frame probe found SteamVR activity `3` (standby), proximity raw `2.25`, and one Battery-type supply named `max1720x_bat_7-36`. It exposed readable `capacity` (89%), `status` (Charging), `voltage_now`, and `current_now`; `power_now` was absent. The owned lock was released. No wake, input, normal service, power setting, or plugin install was touched.

In network/device-isolated, unprivileged **actual Decky 3.3.0 amd64**, the exact adapted archive was discovered. A private Frame-shaped supply fixture produced history and per-app power through public legacy RPC. The complete native regression runner, including existing negative controls, passed. Local managed install/remove tests and the exact-source/manifest guard passed. CI's native ARM64 and fake Frame e2e jobs remain required before merge.

This supports **partial** compatibility. The official frontend initialized in the earlier opaque Chromium audit with backend calls denied; it has not been tested with these live samples. Actual managed recording on Frame ARM64, long-term history, foreground-app attribution, panel controls, and worn VR remain unverified. Existing copies need update or reinstall.

## Hosted ARM64 follow-up

The [main native Decky run](https://github.com/saphid/frame-control/actions/runs/40776292569)
on `dad5f78a02dd477a689689865cd4ef4205b87e22` passed the exact Battery
Tracker case on native amd64 **and ARM64** runners. Both logs report `PASS 67`
for discovery, Frame-shaped private battery samples, history and per-app power
through actual Decky 3.3.0 RPC. These were disposable fixture supplies inside
isolated containers. The managed plugin still has not recorded a real Frame
battery sample; the remaining limits above still apply.
