# Bluetooth 3.1.1 compatibility fixture, 25 October 2026

The unmodified official Decky store archive for Bluetooth 3.1.1 (store ID 18,
SHA-256 `f07f7b74f31da15b5e3a8234a3f00faa01365b56b8f496aca7bb79120be7b8a5`)
passes Frame Control's archive rules. The fake Frame e2e harness installed it
through the store API, verified the managed receipt and frontend bytes, then
removed it. An earlier real Frame check recorded the backend's `Bluetooth
plugin loaded` line while SteamVR was in standby.

In a local Node host test, its official frontend starts and builds an initial
panel tree. Framey supplies empty Steam localization token maps, so the plugin
can use its own fallback labels. The test leaves React effects and click
handlers inert and sends no backend calls. It does not inspect paired devices,
change Bluetooth state, exercise a controller, or prove the panel is visible in
VR. No worn-headset check has passed for this plugin.
