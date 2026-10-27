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
For persistent backend settings, use Decky's `decky.DECKY_PLUGIN_SETTINGS_DIR` rather
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
| API v1 manifest with the modern Decky API initializer | Attempts to render the plugin's panel; recognized legacy IIFE bundles also use the legacy bridge | Pinned Storage Cleaner 1.4.0 archive, fake Frame install/pack test, local Chromium with stub backend. Cleanup actions were not tested. |
| Legacy Decky IIFE frontend, with no API manifest field | Wraps the returned initializer as an ES module inside the same opaque iframe; passes `serverAPI` and preserves the legacy title | MusicControl 1.1.6 exact official archive, local Chromium startup with backend methods blocked; fake Frame installation/pack/removal |
| Legacy `serverAPI.callPluginMethod(method, kwargs)` | Uses Decky's `loader/call_legacy_plugin_method` RPC, preserving keyword arguments and `{success, result}` replies | Fake Frame HTTP/CDP read/write with a synthetic backend; no official plugin backend action or worn VR result |
| Official `@decky/rollup` JSX (`SP_JSX.jsx`, `jsxs`, `Fragment`) | Creates React elements in the isolated panel | Sample bundle smoke test; host unit test |
| `PanelSection`, rows, buttons, toggles, dropdowns | Local touch-sized controls; disabled controls stay inert during a backend call | Local browser and host unit test |
| `TextField`, `SliderField`, grouped `Dropdown` options | Native text, range and select controls in the panel; disabled state, numeric slider callback and basic input types | Host unit test; worn VR use unverified |
| Scrollable panel content | Visible Scroll plugin up/down buttons move the last region reached by a trusted pointer, or the document if that region disappears. Hold either button to repeat; keyboard activation still moves one step. Plugins may use ordinary CSS overflow containers. | Parent/iframe message tests and a real Frame synthetic OpenVR pointer hold; physical controller scroll and hold remain unverified |
| `Tabs`, `SidebarNavigation`, spinners, dialog/menu wrappers, progress bars | Local tab navigation and ordinary HTML controls; no Steam navigation or controller focus tree | Host tests and catalog frontend smoke checks in local Chromium |
| `SteamUIStore` / `DFL.Router.RunningApps`, `MainRunningApp` | Bounded detached Steam CEF reads while the panel is open; refresh about every two seconds; no MobX observation. Failed reads clear stale context. | Locked real Frame empty-list reads; nonempty local Chromium fixtures. Real running-game selection unverified. |
| `GameSessions.RegisterForAppLifetimeNotifications` | Actual Steam callbacks, bounded queue and disposable `.unregister()` handle; no events inferred from snapshot changes; lease cleanup after lost panels | Real Frame registration/poll/close; launch/exit, retry, expiry and duplicate tests use explicit fixtures. Real game transitions unverified. |
| Other `SteamClient` subscriptions | Explicit inert registration methods return disposable handles; no fabricated power/input/game-action events. Mutating Steam/power methods are unavailable. | Host contract tests; safe fallbacks only |
| `DialogCheckbox`, `DialogButtonPrimary` | Native checkbox and button controls in the panel | Host unit test; Storage Cleaner empty-data browser check |
| Optional `settings`, `frameyQuickActions` | Separate settings tab when content also exists; settings-only plugins have no empty Panel tab; up to eight actions with result text | Host unit test; these fields are Framey additions |
| `serverAPI.call` / `callable` | Calls only that plugin's Decky Python backend via the headset service | Fake Frame e2e; real ARM64 Notebook save/reopen across backend restart and Simple Timer settings/recents persistence via local Chromium. No worn-VR claim. |
| API v1/v2 `addEventListener` / `removeEventListener` | Plugin-scoped real backend events while panel is open; bounded queue, about one-second polling, subscription expiry | Real ARM64 Simple Timer countdown, start/cancel and completion toast via local Chromium; scope/bounds/reconnect tests. No closed-panel notifications. |
| `toaster.toast` | Visible toast inside the plugin panel; plain text or React nodes for title, body, icon, logo and subtext; `dismiss` and optional `onClick` | Host unit test; no Steam system notification or worn VR check |
| `localStorage` | Synchronous, per-plugin cache backed by the Frame Control panel origin. Up to 64 keys, 64 KiB per value and 128 KiB total; `clear()` removes only this plugin's cache. Falls back to memory if panel storage is denied. | Parent/iframe round-trip and reopen in the local host test; real headset persistence remains unverified. |
| `SteamClient.Storage.GetJSON` / `SetObject` | Uses the same bounded per-plugin cache; a missing key rejects with `Not found`. It cannot read Steam account or global storage. | Host contract tests and local Chromium settings views; headset persistence after reopen remains unverified. |
| IndexedDB / localForage | IndexedDB is deliberately absent inside the opaque iframe so feature detection chooses the bounded localStorage driver. Plugins requiring IndexedDB directly remain unsupported. | HLTB official frontend in local Chromium: its previous `IDBFactory.open` SecurityError disappeared. No live HLTB data request was run. |
| `routerHook.addRoute` / `removeRoute`, `Navigation.Navigate` / `NavigateBack`, `useParams` | Local routes inside this plugin panel, with named segments such as `/plugin/game/:appid/:view?`; `useParams()` reads the current segment values. Back walks up to 32 local page transitions and skips routes removed since navigation. | Host unit test; VR navigation unverified |
| `routerHook.addPatch`, global components | No-op; cannot patch Steam routes | Not applicable |
| `findModule`, `findModuleChild`, `findModuleExport`, class lookup and module mapping | Searches a finite registry of Framey controls and CSS maps. Unknown Steam modules return `undefined` or an empty mapping. The optional UI-audio export cannot play sound. | Host contract tests; pinned TabMaster 2.15.1 QAM and documentation render in local Chromium. Steam library editing and worn VR remain unverified. |
| `Navigation.CloseSideMenus` | Returns to this plugin's main panel | Pinned HLTB for Deck 2.0.12 shallow settings view in local host test. Live HLTB search remains unverified. |
| `Focusable.onActivate`, `showModal`, `ConfirmModal` | Pointer and Enter/Space activation, disabled state, and local confirmation dialogs with cancel/close and nested-dialog focus | Host tests and official AlarMe 1.6.3 timer/preset controls with a real ARM64 backend in local Chromium. Sound, suspend and worn VR remain unverified. |
| Steam library/store patches, CEF tab injection | Unavailable; no matching target in the isolated panel | Frame CEF inspection |
| `fetchNoCors`, file picker, root calls | Unavailable | Not supported by Framey |

Keep routes local to the panel and give every operation a visible result. A
plugin that calls `Navigation.Navigate('/decky/store')` will not open the
Frame Control store; only paths registered by that same plugin can navigate.
Optional route segments must be at the end. Framey accepts local path segments
only; query strings, external URLs, Steam library routes and duplicate parameter
names are rejected. Removing an active route returns to the plugin panel.
`Navigation.NavigateBack()` returns to the preceding local page, then the
plugin root. `Navigation.CloseSideMenus()` returns directly to the root and
clears that panel's history. Neither operation navigates Steam's own UI.
Toasts stay inside the panel, so keep essential errors in the plugin UI too.
Treat module lookup results as Framey-local exports. Do not depend on Steam
webpack IDs, function-source signatures, or Steam-only CSS class names; a
lookup that works in the Steam Deck QAM can still return `undefined` here.
Use a local control or a visible unsupported message when it does. For a
confirmation, call `showModal` with a `ConfirmModal` and keep any irreversible
operation behind its OK action. `Focusable.onActivate` accepts pointer and
Enter/Space input in Framey, but only a worn-headset test can establish how a
physical controller reaches it. See the
[module lookup evidence](evidence/framey-module-lookup-2026-10-26.md) and
[dialog control evidence](evidence/framey-dialog-controls-2026-10-26.md) for
the exact tested official versions.
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
