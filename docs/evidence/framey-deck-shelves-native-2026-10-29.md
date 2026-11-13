# Deck Shelves 2.0.0 native settings probe, 29 October 2026

The unchanged official archive for store ID 135 has SHA-256
`b566280ad38fd3ecd584b5b46a855f301539eb9a86063834c64b7045f7063f91`.
The earlier [browser evidence](framey-deck-shelves-browser-2026-10-26.md)
proved only local frontend settings rendering and a stubbed Python backend.

`python3 scripts/framey-test-decky-runtime.py --case 135 --output /tmp/framey-deck-shelves-native-20261029.json`
passed with the published Decky 3.3.0 x86_64 loader in a disposable container
with no external network, host devices, session bus or user home. Decky
discovered the official API v1 plugin. Its public `get_settings` returned
disabled defaults; `set_settings` saved one private test shelf; the JSON file
and a fresh `get_settings` agreed. The same shelf ID and title returned after
stopping and restarting the Decky loader. The runner removed its container
and image. No headset lock, real Frame service, Steam library or external
account was used.

This verifies only private backend settings persistence. The plugin's primary
Steam Home shelf injection has no verified target in Framey's isolated panel.
Real Frame ARM64 settings, wearer-visible VR and physical controller input
remain unverified. Deck Shelves stays **partial**; compatibility counts do not
change.
