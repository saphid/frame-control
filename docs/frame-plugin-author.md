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
for API v2 Decky frontend bundles and API v1 bundles that use Decky's modern
frontend API initializer. It renders common settings controls in the
separate SteamVR dashboard panel, but Steam library and store page patches
remain unavailable. Wearer-visible use is not yet verified.
The [settings sample](../examples/framey-settings/README.md) shows an official
Decky JSX build, backend persistence, a toggle and a local toast. Framey offers
only official-store-owned plugins in its VR panel.
For persistent backend settings, use Decky's `decky.decky_SETTINGS_DIR` rather
than assuming an environment variable or Steam Deck home path. Validate stored
types when reading, write through a temporary file before replacing the old
file, and give the panel a safe default if settings are missing or damaged.
Removing a managed plugin leaves its Decky settings behind; document how users
can reset data your plugin owns.

To test safely, use a separate Frame Control managed Decky install, verify the
ZIP digest from the official store, install one plugin at a time, and inspect
`journalctl --user -u frame-control-decky.service`. Remove only your own
plugin folder when you finish. See the current [compatibility table](decky-frame.md).

## Framey Decky API compatibility

Framey hosts a plugin's frontend in an isolated iframe in the Frame Control
SteamVR panel. The table describes the current implementation and its tests;
none of these frontend controls has passed a worn-headset check yet.

| Decky API or UI feature | Framey behavior | Verified in |
| --- | --- | --- |
| `definePlugin` with `content`, `titleView` | Renders a React panel and optional title | Local browser with ProtonDB Badges; host unit test |
| API v1 manifest with the modern Decky API initializer | Attempts to render the plugin's panel; older API v1 bundles still show an incompatibility message | Pinned Storage Cleaner 1.4.0 archive, fake Frame install/pack test, local Chromium with stub backend. Cleanup actions were not tested. |
| Official `@decky/rollup` JSX (`SP_JSX.jsx`, `jsxs`, `Fragment`) | Creates React elements in the isolated panel | Sample bundle smoke test; host unit test |
| `PanelSection`, rows, buttons, toggles, dropdowns | Local touch-sized controls; disabled controls stay inert during a backend call | Local browser and host unit test |
| `TextField`, `SliderField`, grouped `Dropdown` options | Native text, range and select controls in the panel; disabled state, numeric slider callback and basic input types | Host unit test; worn VR use unverified |
| `DialogCheckbox`, `DialogButtonPrimary` | Native checkbox and button controls in the panel | Host unit test; Storage Cleaner empty-data browser check |
| Optional `settings`, `frameyQuickActions` | Separate settings tab; up to eight actions with result text | Host unit test; these fields are Framey additions |
| `serverAPI.call` / `callable` | Calls only that plugin's Decky Python backend via the headset service | Fake Frame e2e for setting read/write across CEF calls, update, and reinstall; host unit test. Real Decky persistence remains unverified. |
| `toaster.toast` | Visible toast inside the plugin panel; `dismiss` and optional `onClick` | Host unit test; no Steam system notification |
| `localStorage` | Synchronous, per-plugin cache backed by the Frame Control panel origin. Up to 64 keys, 64 KiB per value and 128 KiB total; `clear()` removes only this plugin's cache. Falls back to memory if panel storage is denied. | Parent/iframe round-trip and reopen in the local host test; real headset persistence remains unverified. |
| `routerHook.addRoute` / `removeRoute`, `Navigation.Navigate` / `NavigateBack`, `useParams` | Local routes inside this plugin panel, with named segments such as `/plugin/game/:appid/:view?`; `useParams()` reads the current segment values | Host unit test; VR navigation unverified |
| `routerHook.addPatch`, global components | No-op; cannot patch Steam routes | Not applicable |
| `findModuleChild`, `Navigation.CloseSideMenus` | Steam module lookup returns `null`; close returns to this plugin's main panel | Pinned HLTB for Deck 2.0.12 entry point and shallow settings view in local host test. Steam library patch and live HLTB search remain unverified. |
| Steam library/store patches, CEF tab injection | Unavailable; no matching target in the isolated panel | Frame CEF inspection |
| `fetchNoCors`, Decky event listeners, file picker, root calls | Unavailable | Not supported by Framey |

Keep routes local to the panel and give every operation a visible result. A
plugin that calls `Navigation.Navigate('/decky/store')` will not open the
Frame Control store; only paths registered by that same plugin can navigate.
Optional route segments must be at the end. Framey accepts local path segments
only; query strings, external URLs, Steam library routes and duplicate parameter
names are rejected. Removing an active route returns to the plugin panel.
Toasts stay inside the panel, so keep essential errors in the plugin UI too.
An API v1 manifest does not guarantee a working Framey panel. Test the exact
store archive and do not assume SteamClient app details, library patches, or
destructive actions work in VR. The
[Storage Cleaner browser check](evidence/framey-api-v1-browser-2026-10-25.md)
used empty stub data and did not invoke its cleanup actions.
Use the Decky Python backend for settings that must survive browser cache loss.
The Framey `localStorage` bridge is for disposable frontend caches, including
the cache read attempted by Steam Status 1.2.3. It does not expose another
plugin's cache or the Frame Control UI key. A real Steam Status panel reopen
and a worn-headset settings check are still needed.

HLTB for Deck 2.0.12 demonstrates the limit of the panel shim: its official
bundle can start and produce a settings view with Framey's Steam module lookup
stub, but its game page and context menu patches have no Steam target in the
isolated panel. The tests do not call its HLTB network search or Python backend.
Do not claim game length badges work in VR from this result.
