# Deck Shelves chunked frontend, 26 October 2026

The exact official Deck Shelves 2.0.0 archive (store ID 135, SHA-256 `b566280ad38fd3ecd584b5b46a855f301539eb9a86063834c64b7045f7063f91`) contains `dist/index.js` and eight JavaScript chunks. Its API v1 `connect(1, "Deck Shelves")` bridge sits in `chunks/decky-api-WgbNuFYS.js`, not in the entry file; the original static scanner therefore reported its frontend API as unknown. Framey's prior blob import failed before initialization because a blob URL has no directory in which to resolve `./chunks/...`. The [numeric observation](framey-deck-shelves-browser-2026-10-26.json) and [local Chromium capture](framey-deck-shelves-browser-2026-10-26.png) record a targeted follow-up using the unchanged official frontend.

Framey now serves JavaScript files from the managed plugin's `dist` directory using hierarchical module URLs. Its opaque `allow-scripts` iframe still has no Frame UI key. Local Chromium received HTTP 200 for the entry and eight chunks, reported the initializer ready, and rendered the settings panel with “Enable shelves on Home,” “Create default shelves,” “Behavior,” and “Shelves.” The browser audit denied the attempted `get_settings` backend call, Steam library read and plugin network access. No backend method executed.

The catalog moves this exact version from broken to **partial** for visible local settings. The plugin's main feature injects shelves into Steam Home; Framey has no verified Steam Home patch target. Actual Decky RPC, real Frame settings, wearer-visible VR, and physical controller input remain unverified. The [compatibility table](../framey-compatibility.md) and store views retain these limits.

## Isolated official backend settings check

I verified the same archive digest before loading its unchanged `Deck-Shelves/main.py` in local Python. A stub `decky` module supplied only a logger; `DECKY_PLUGIN_SETTINGS_DIR` and `DECKY_HOME` pointed inside a temporary directory. No Decky service, headset, Steam API, or network call was involved. Calling `_main`, `get_settings`, and `set_settings` returned the default disabled state, saved one shelf named `Local Test`, and returned that shelf from a fresh `Plugin` instance. The temporary directory was removed after the check.

```json
{"archiveSha256":"b566280ad38fd3ecd584b5b46a855f301539eb9a86063834c64b7045f7063f91","defaultEnabled":false,"defaultShelves":0,"saveResult":true,"reopenedEnabled":true,"reopenedShelfTitle":"Local Test","settingsFileExists":true}
```

This proves only the archive's Python settings logic under those local conditions. It does not prove that Decky 3.3.0 can dispatch these methods on the ARM64 Frame, that the opaque panel can save settings through the production bridge, or that a shelf appears on Steam Home or in VR.

## Exact source real Frame gates

The exact source commit `b0c4647b856035c970ae27ea4e2ddbf6e51f6963` ran the unattended `scripts/framey-vr-check.py --exercise` on SteamOS build `20261022.6153909` under its unique shared-lock owner. Preflight found SteamVR activity 3 (standby), battery 100%, and proximity 6.25. The repository sample panel appeared, stereo compositor pixels changed, and `/dev/video99` supplied a mirror frame. Synthetic OpenVR pointer input changed the sample setting through actual Decky; the value survived a fresh iframe reopen. Native scroll did not move. The runner removed its temporary services and recovery timer, read back the original `false`/`5` power values, found battery 99%, reported no cleanup errors, and released its lock.

The same source then passed `scripts/frame-smoke.sh` **13/13** on the real Frame, starting from standby at battery 99%. Its final cleanup step passed. The [sanitized result fields](framey-deck-shelves-browser-2026-10-26.json) omit room pixels, raw overlays, identifiers, and settings contents; private captures were not committed. These gates exercise the Framey repository sample and generic install/launch/remove paths. They do **not** exercise Deck Shelves' official ARM64 backend or prove its settings or shelves in VR. No person wore the headset and no physical controller was checked.
