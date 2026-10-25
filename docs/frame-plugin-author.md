# Write a plugin for Frame

There are two paths. Choose the one that matches your feature.

## Frame Control extension

Use a Frame Control extension for a panel, status view, or guide that does not
need to change the headset. Put `extension.json` and `index.html` in one folder
under `~/.local/share/frame-control/extensions`. The opt-in headset panel lists
the folder and opens it in a sandboxed iframe. The version 1 bridge has only
`capabilities` and read-only `status`. It cannot call Steam, change settings,
or run privileged code. See [the extension API](extensions.md) and its example.

## Decky plugin

Use a Decky plugin only if you need Decky's backend or Gamepad UI integration.
Build an official-format ZIP with one top-level folder, `plugin.json`, and a
frontend bundle in `dist/index.js`. A Python `main.py` backend is optional.
Test on ARM64. If you ship an ELF helper, build it for AArch64 (ELF machine
183). Avoid root, `sudo`, Steam Deck TDP controls, fixed x86 binaries, and
paths under `/etc`. Frame Control's managed loader is a normal user service;
it blocks root plugins and x86 archives. Keep data under your plugin folder or
the user's home directory, and provide a removal path.

The current Frame SteamVR shell does not expose Decky's Steam Deck Quick Access
Menu. A backend `Loaded` log only proves backend startup. Test any frontend
page, setting, notification, route, and controller input while wearing a Frame
before describing it as working in VR. Until a QAM bridge is verified, a Frame
Control extension is the simplest route for a self-contained read-only VR panel.

Frame Control now has an experimental [Framey panel host](framey-loader.md)
for API v2 Decky frontend bundles. It renders common settings controls in the
separate SteamVR dashboard panel, but Steam library and store page patches
remain unavailable. Wearer-visible use is not yet verified.

To test safely, use a separate Frame Control managed Decky install, verify the
ZIP digest from the official store, install one plugin at a time, and inspect
`journalctl --user -u frame-control-decky.service`. Remove only your own
plugin folder when you finish. See the current [compatibility table](decky-frame.md).
