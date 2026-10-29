# Game Sync 1.0.4 isolated backend check, 29 October 2026

The official Decky archive for Game Sync (ID 104) is 2,228,806 bytes with
SHA-256 `65e021ebb37d2ebfbfbe3dbc8af95aef9556cf484730362c6b26c4ecc3e62ccd`.
Its unmodified ZIP is pinned as `tests/fixtures/framey-official/104.zip`.

`python3 scripts/framey-test-decky-runtime.py --case 104 --output /tmp/framey-gamesync-native-104.json`
passed with the published Decky 3.3.0 x86_64 loader, SHA-256
`e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181`.
The disposable container had no external network or host devices, dropped
capabilities and used a private home. The real loader discovered the exact
plugin. Its `get_config` returned defaults with automatic game sync and
capture upload disabled. A private `advanced_mode` setting changed from false
to true and remained true after the loader restarted. The runner removed its
container and image; a separate `docker ps` and image-list audit found no
owned resources.

The original opaque-iframe browser audit blocked `get_config` before panel
initialization completed, so it did not prove a usable frontend. This native
test confirms only a configuration backend path. No cloud authentication,
rclone download or sync, screenshot deletion, process signal, game event,
real Frame backend, VR visibility or physical controller was exercised.
The published `rclone_manager.py` names an amd64 rclone download, so this
result does not establish ARM64 sync support. Game Sync remains **partial**.
