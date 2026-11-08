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
Keep setting mutations disabled after a failed backend read until an explicit
reload succeeds. An initial display default or a stale value is not a recovered
saved setting. The settings sample demonstrates this guard for its toggle and
Reset action, including callbacks retained before React redraws.
Treat a rejected save reply as an uncertain outcome: the backend may have
committed before the connection failed. Disable further edits until a new read
succeeds, display that returned value, and do not announce the failed request
as saved. The sample applies this rule to both the toggle and Reset dialog;
after a Reset error, close the dialog and reload before trying again.
Retire a settings view's callbacks on unmount and ignore replies from its old
read/write requests. Close dialogs owned by that view, and read saved settings
again when it mounts. Cleanup does not cancel a backend request already sent;
it prevents that old view from issuing new requests or announcing stale UI
results. The sample uses a request generation as well as an active-view guard
so React's development effect replay cannot let an old read unlock a newer one.

Give text fields a visible `label` or an explicit `aria-label`; Framey preserves
the latter on the native input. This includes Wine Cellar 0.2.1's published
installed-game search, tested with synthetic search text in the local host.
Accessible-name preservation does not prove VR keyboard or controller usability.

To test safely, use a separate Frame Control managed Decky install, verify the
ZIP digest from the official store, install one plugin at a time, and inspect
`journalctl --user -u frame-control-decky.service`. Remove only your own
plugin folder when you finish. See the current [compatibility table](decky-frame.md).

Before publishing, check your local ZIP with Frame Control's installer rules:

```sh
python3 scripts/framey-check-archive.py path/to/plugin.zip --name 'Exact Decky store name'
```

The checker reads only that local ZIP. `installerAccepted` means its structure,
size, flags and included binaries pass the same archive validator used by the
managed store. `panelCandidate` means the basic frontend entry and API version
can be admitted to Framey's panel. Neither result proves that the published
store digest matches this ZIP, Decky discovers its backend, or its UI works in
VR. The [sample plugin](../examples/framey-settings/README.md#build) includes a
complete pack-and-check command.

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
| `Field.icon`, `ToggleField.icon`, `ButtonItem.icon` | Keeps the plugin's React icon beside the field label, including its supplied SVG geometry, title, class and style. | Exact Simple Timer 1.0.0 Subtle Mode toggle and speaker icon in real React/DOM with a synthetic save callback; enabled/disabled transitions, plus local Field/ButtonItem icon fixtures. No timer backend, audio playback, controller or worn VR proof. |
| `Dropdown.onMenuWillOpen(showMenu)` | A Load options action invokes the plugin's loader. Choices become selectable only after `showMenu()`; Reload options invokes it again. Cancel loading hides the wait and rejects late callbacks. | Exact published Wine Cellar 0.2.1 option-loader callback with synthetic tool replies; host contract tests. No live helper or worn VR check. |
| `Dropdown.renderButtonValue` | Renders a plugin-supplied current-value view above the native select or deferred loader. Receives the matching option's label, or the default label when no choice matches; the original option object still reaches `onChange`. | Exact published Wine Cellar 0.2.1 renderer/control in real React/DOM with synthetic tool choices: initial/loading/updated/disabled values, styles, accessible label and empty-string selection. No real tool discovery/assignment, backend or worn VR proof. |
| `TextField.defaultValue`, `onBlur`, `onFocus`, `onClick`, `onKeyDown`, `onKeyUp` | Uncontrolled input drafts and original React events reach the plugin callbacks; disabled fields suppress callbacks. A controlled `value` takes precedence over `defaultValue`. | Local host contracts and the exact Game Sync 1.0.4 text-dialog function: edited draft/OK and Cancel. No sync, backend, real input device or VR keyboard check. |
| `TextField.focusOnMount` | Focuses an enabled native input when it mounts. A modal preserves focus already inside it, falling back to its shell when nothing inside has focus. Updating an existing field does not refocus it. | Exact RadiYo! 1.3 text dialog in real React/DOM with synthetic query input; opt-out, disabled, update, shell fallback and focus restoration checks. No radio backend, physical controller or VR keyboard proof. |
| `TextField.bShowClearAction`, `bAlwaysShowClearAction` | An opt-in Clear button empties the input through its native React change event. It hides when empty unless always-visible is requested; disabled fields stay inert. | Pinned Wine Cellar 0.2.1 search-control fixture; automated React/DOM check requires Linux Chrome. Worn VR remains unverified. |
| `TextField.inlineControls` | Renders the plugin's supplied React controls after the input and built-in actions. Supplied controls retain their own callbacks, styles and disabled state. | Exact Web Browser 1.4.3 favorite-folder component in real React/DOM with an in-memory favorites stub: empty-name disabled action, edited draft/parent path, existing-folder guard and nested-dialog callback. No real favorites, browser tabs, backend, physical input or VR keyboard proof. |
| Scrollable panel content | Visible Scroll plugin up/down buttons move the last region reached by a trusted pointer, or the document if that region disappears. Hold either button to repeat; keyboard activation still moves one step. Plugins may use ordinary CSS overflow containers. | Parent/iframe message tests and a real Frame synthetic OpenVR pointer hold; physical controller scroll and hold remain unverified |
| `Tabs`, `SidebarNavigation`, spinners, dialog/menu wrappers | Local tab navigation and ordinary HTML controls; no Steam navigation or controller focus tree | Host tests and catalog frontend smoke checks in local Chromium |
| `MenuGroup.label`, `disabled` | A labeled native fieldset; disabling it blocks native activation and focus of descendant controls, including nested groups. Individual `MenuItem` disabled states still apply. | Exact TabMaster 2.15.1 Micro SD Card menu with synthetic cards/preset callbacks in real React/DOM. No card discovery, real library edit, Steam submenu or worn/controller proof. |
| `SidebarNavigation.pages` with `"separator"` entries | Omits layout separators from the local tab strip so they cannot open blank pages. Hidden pages stay absent; changing visibility of an earlier page preserves a later page's selection at the same source index. | Exact published Game Sync 1.0.4 navigation replay with inert child views and synthetic tab selection. No sync, backend, physical-input or worn VR proof. |
| `ReorderableList` | Lists plugin entries by `position`; native Move up/down buttons edit a draft. Save order calls `onSave` with normalized positions; Cancel discards the draft. Labels, data and optional `interactables` are retained. `disableReordering` hides ordering controls. | Exact published TabMaster 2.15.1 list/save callback with synthetic entries; cancel, disabled/late handlers, failed-save retry and refreshed-list tests. No real library edit or physical controller check. |
| `ProgressBar`, `ProgressBarItem`, `ProgressBarWithInfo` | Native progress control; `indeterminate` omits its value so it animates as unfinished. Item and WithInfo preserve React `label` and `description` content, and WithInfo shows `sOperationText`. Estimated completion time is not shown. | Exact Emuchievements 2.0.5 progress expressions in real React/DOM with synthetic loading errors and achievement counts; label, markup/styles, updates and indeterminate progress verified. No achievement service, live backend, controller or worn VR proof. |
| `SteamUIStore` / `DFL.Router.RunningApps`, `MainRunningApp` | Bounded detached Steam CEF reads while the panel is open; refresh about every two seconds; no MobX observation. Failed reads clear stale context. | Locked real Frame empty-list reads; nonempty local Chromium fixtures. Real running-game selection unverified. |
| `GameSessions.RegisterForAppLifetimeNotifications` | Actual Steam callbacks, bounded queue and disposable `.unregister()` handle; no events inferred from snapshot changes; lease cleanup after lost panels | Real Frame registration/poll/close; launch/exit, retry, expiry and duplicate tests use explicit fixtures. Real game transitions unverified. |
| Other `SteamClient` subscriptions | Explicit inert registration methods return disposable handles; no fabricated power/input/game-action events. Mutating Steam/power methods are unavailable. | Host contract tests; safe fallbacks only |
| `DialogCheckbox`, `DialogButtonPrimary` | Native checkbox and button controls in the panel | Host unit test; Storage Cleaner empty-data browser check |
| Optional `settings`, `frameyQuickActions` | Separate settings tab when content also exists; settings-only plugins have no empty Panel tab; up to eight actions with result text | Host unit test; these fields are Framey additions |
| `serverAPI.call` / `callable` | Calls only that plugin's Decky Python backend via the headset service | Fake Frame e2e; real ARM64 Notebook save/reopen across backend restart and Simple Timer settings/recents persistence via local Chromium. No worn-VR claim. |
| API v1/v2 `addEventListener` / `removeEventListener` | Plugin-scoped real backend events while panel is open; bounded queue, about one-second polling, subscription expiry | Real ARM64 Simple Timer countdown, start/cancel and completion toast via local Chromium; scope/bounds/reconnect tests. No closed-panel notifications. |
| `toaster.toast` | Visible toast inside the plugin panel; plain text or React nodes for title, body, icon, logo and subtext; `dismiss` and optional `onClick` | Host unit test; no Steam system notification or worn VR check |
| `localStorage` | Synchronous, per-plugin cache backed by the Frame Control panel origin. Up to 64 keys, 64 KiB per value and 128 KiB total; `clear()` removes only this plugin's cache. Failed writes stay in parent-page memory across plugin reopen until a write succeeds. Reloading that page loses the fallback and may restore older disk values. Plugin code waits for the cache reply; a missing or invalid reply displays an error after five seconds instead of opening with empty saved settings. | Parent/iframe round-trip, delayed reply, timeout, denied/quota-exceeded writes, plugin isolation, storage recovery and reopen in the local host test; real headset persistence remains unverified. |
| `SteamClient.Storage.GetJSON` / `SetObject` | Uses the same bounded per-plugin cache; a missing key rejects with `Not found`. It cannot read Steam account or global storage. | Host contract tests and local Chromium settings views; headset persistence after reopen remains unverified. |
| IndexedDB / localForage | IndexedDB is deliberately absent inside the opaque iframe so feature detection chooses the bounded localStorage driver. Plugins requiring IndexedDB directly remain unsupported. | HLTB official frontend in local Chromium: its previous `IDBFactory.open` SecurityError disappeared. No live HLTB data request was run. |
| `routerHook.addRoute` / `removeRoute`, `Navigation.Navigate` / `NavigateBack`, `useParams` | Local routes inside this plugin panel, with named segments such as `/plugin/game/:appid/:view?`; `useParams()` reads the current segment values. Back walks up to 32 local page transitions and skips routes removed since navigation. | Host unit test; VR navigation unverified |
| `routerHook.addPatch`, global components | No-op; cannot patch Steam routes | Not applicable |
| `findModule`, `findModuleChild`, `findModuleExport`, class lookup and module mapping | Searches a finite registry of Framey controls and CSS maps. Unknown Steam modules return `undefined` or an empty mapping. The optional UI-audio export cannot play sound. | Host contract tests; pinned TabMaster 2.15.1 QAM and documentation render in local Chromium. Steam library editing and worn VR remain unverified. |
| `findInTree`, `findInReactTree` | Searches objects and arrays supplied by the plugin, returning the first matching object. `walkable` restricts object keys and `ignore` skips them; React search follows only `props`, `children`, `child` and `sibling`. Cycles terminate. `getReactRoot()` still returns `null`. | Exact published Emuchievements 2.0.5 settings migration and reopen with synthetic legacy RPC replies; nested values, including empty strings, survive. No real account, backend, Steam-tree access or worn VR proof. |
| `Navigation.CloseSideMenus` | Returns to this plugin's main panel | Pinned HLTB for Deck 2.0.12 shallow settings view in local host test. Live HLTB search remains unverified. |
| `Focusable.onActivate`, `showModal`, `ConfirmModal` | Pointer and Enter/Space activation, disabled state, and local confirmation dialogs with cancel/close and nested-dialog focus | Host tests and official AlarMe 1.6.3 timer/preset controls with a real ARM64 backend in local Chromium. Sound, suspend and worn VR remain unverified. |
| `showContextMenu(...).Hide()` / `.Show()` | Opens a local dialog shell. Hide dismisses only that menu; Show remounts dismissed content and does nothing while visible. The instance retains its original focus target. | Exact TabMaster 2.15.1 menu factory/Hide callback with an inert library view; real React/DOM reopen, focus and nested-dialog checks. No real library edit, Steam popup or worn/controller proof. |
| `ColorPickerModal` | Local hue, saturation, lightness and alpha sliders with a preview. Defaults initialise the draft; OK passes an `hsla(...)` string to `onConfirm`. Cancel/Close discards it. A returned promise disables editing until success or a visible retryable failure. | Exact published CSS Loader 2.1.3 picker/callback replay with a synthetic setter, including draft/cancel, stale callbacks and async retry. No theme, Steam, backend or worn VR proof. |
| `SimpleModal` | Local content wrapper within `showModal`. `active={false}` unmounts its children; true or omitted renders them. The existing shell owns focus and dismissal. | Exact Web Browser 1.4.3 warning replay, including accept and shell cancellation; real React/DOM checks child styles, focus restoration and inactive-child cleanup/remount. No full Web Browser/DeckSP, Steam portal, backend, controller or worn VR proof. |
| `ModalRoot.onOK` | An explicit local OK button calls the handler; `bOKDisabled` disables it. The handler owns dismissal through `closeModal`. Returned promises block repeat submissions and that dialog's Close/Escape; failures remain visible for retry. Roots without `onOK` add no button. | Exact RadiYo! 1.3 text-dialog replay with synthetic text; radio search, playback, VR keyboard and physical controllers unverified. |
| Custom `ModalRoot.onCancel`, `onEscKeypress` | A custom dialog that passes its injected `closeModal` to `ModalRoot` binds those handlers to its own shell. Close calls `onCancel`; Escape uses `onEscKeypress` when present, otherwise cancels. Updated or unmounted roots retire their old handlers. | Exact Decky Localsend 0.4.5 receive dialog in real React/DOM, recording synthetic decisions only. No real offer, backend, file transfer or worn VR proof. |
| Steam library/store patches, CEF tab injection | Unavailable; no matching target in the isolated panel | Frame CEF inspection |
| `fetchNoCors`, file picker, root calls | Unavailable | Not supported by Framey |

For plugin-cache values, use `getItem`, `setItem` and `removeItem`.
`key in localStorage` also recognizes saved keys, including empty strings.
Pinned Game Sync 1.0.4 uses this to mark a game as out of sync. Its published
cache callbacks now retain that marker across panel reopen in an offline
host/parent replay; this does not prove actual synchronization, live headset
persistence or worn visibility.

Use `MenuGroup` to label related actions and set `disabled` when their prerequisite
is unavailable. Framey uses native fieldset inheritance, so an enabled nested
group cannot enable its controls inside a disabled parent. This governs native
controls; it does not guard a plugin directly calling its own callbacks or
implement Steam submenus or a controller focus tree.

Keep the instance returned by `showContextMenu` when a menu action needs to call
`Hide()`. Hiding is programmatic dismissal and does not invent a cancellation
result. `Show()` reopens the same element with fresh component state after Hide,
shell Close or Escape; it cannot duplicate a menu already open. Focus returns
to the original opener when it still exists and no other dialog remains open.
Menu actions do not automatically dismiss the menu, so plugins can keep
interactive choices open. Steam popup positioning, `bRetainOnHide`, submenus and
controller navigation are not implemented by this local handle.

For a custom dialog, pass the `closeModal` injected by `showModal` into your
inner `ModalRoot`. That binds its `onCancel` and `onEscKeypress` to the correct
dialog, including when another dialog opens above it. A registered root handler
takes precedence over the outer component's handler for the same action. Close
calls cancellation and dismisses the dialog; a custom Escape handler owns its
own dismissal. Calling the returned handle's `Close()` programmatically only
closes it and does not invent a cancellation result. Resolve any plugin-owned
pending decision explicitly on that path. Returned `onOK` promises continue to
block Close and Escape while submission is pending.

For `TextField`, set `bShowClearAction` to offer Clear. A controlled field must
update `value` in `onChange`, just as it does for typed edits; the callback can
read the empty string from `event.currentTarget.value` or `event.target.value`.
Uncontrolled `defaultValue` fields also support clearing. Combine
`bShowClearAction` with `bAlwaysShowClearAction` to keep the button visible when
empty. Clearing an already empty input emits no extra change.

Set `focusOnMount` when a new `TextField` should receive native document focus.
Leave it false or omit it when opening a view should keep focus elsewhere.
Disabled fields do not receive initial focus. This flag does not open a Steam
or VR keyboard, provide Steam component ref handles, or implement a controller
focus tree. Worn visibility, physical controller input and the VR keyboard still
require checks on the headset.

For `SliderField`, supply a finite `resetValue` within `min` and `max` to show
a Reset button. It sends the numeric default through the same `onChange(value)`
callback as a slider adjustment, so save it through the normal setting path.
`disabled` also disables Reset. The exact published Battery Tracker 0.2.0
lookback control is replayed in local host tests with synthetic history replies;
real history, controller activation and worn VR remain unverified.

Supply `validValues: value => boolean` to reject values outside a plugin's
allowed set. Framey applies this predicate to slider adjustments, editable
numeric input and Reset; a rejected reset default is not offered. For example,
`validValues: value => [1, 2, 4, 8].includes(value)` allows only those worker
counts. This callback contract is tested with synthetic settings in real
React/DOM, not a published plugin or live backend. The `validValues: 'steps'`
and `'range'` modes have no additional behavior in Framey; native `min`, `max`
and `step` constraints still apply. Worn/controller use remains unverified.

Open `ColorPickerModal` with `showModal` and supply numeric `defaultH` (0–360),
`defaultS` and `defaultL` (0–100), and `defaultA` (0–1). These initialise one
local draft, rather than changing whenever props redraw. OK calls
`onConfirm('hsla(H, S%, L%, A)')`; slider edits and cancellation do not call it.
Return a backend save promise from `onConfirm` to keep the dialog open on
failure and permit retry. A callback that starts a save without returning its
promise cannot report that save's outcome to the picker. Closing the dialog
does not cancel a backend request already sent. This control cannot apply
CSS Loader themes or change Steam's UI by itself.

Wrap custom dialog content in `SimpleModal` and open it through `showModal`.
In Framey, `active` defaults to true. Setting it false unmounts children,
including their effects and local state; reactivation creates a fresh view.
It hides only content: call the injected `closeModal()` or the returned
handle's `Close()` to dismiss the owning shell and resolve `ClosedPromise`.
The wrapper adds no OK/Cancel actions or Steam portal. Existing shell Close
and Escape behavior still applies. A plugin's `onCancelButton` controller
binding is not established by this wrapper or the browser fixture.

Keep routes local to the panel and give every operation a visible result. A
plugin that calls `Navigation.Navigate('/decky/store')` will not open the
Frame Control store; only paths registered by that same plugin can navigate.
Optional route segments must be at the end. Framey accepts local path segments
only; query strings, external URLs, Steam library routes and duplicate parameter
names are rejected. Removing an active route returns to the plugin panel.
`Navigation.NavigateBack()` returns to the preceding local page, then the
plugin root. `Navigation.CloseSideMenus()` returns directly to the root and
clears that panel's history. Neither operation navigates Steam's own UI.
For a dropdown that fetches its choices on demand, populate `rgOptions` and
call the `showMenu` callback passed to `onMenuWillOpen` when the options are
ready. Framey presents a Load options action followed by a native select;
it does not open a Steam context menu. A resolved promise alone does not expose
the choices. Return the promise if you want Framey to display its rejection,
or show the error in your plugin. Cancel loading ends Framey's wait, leaving
your own request lifecycle under your plugin's control; the user can then retry.
Supply `renderButtonValue(label)` when the currently assigned value needs a
custom view, especially before deferred choices are loaded. Framey renders its
React result above the loader/select, including while disabled or waiting.
The argument is the original matching option's label (including a React node),
or `strDefaultLabel` / "Choose an option" if no option matches. Selection uses
`option.data`, so zero and empty strings remain valid choices. This renderer
does not load choices or submit a selection; retain `onMenuWillOpen` and
`onChange` for those operations. The native select keeps its own option text.
Toasts stay inside the panel, so keep essential errors in the plugin UI too.
For a `ReorderableList`, give each entry a `label`, a numeric `position` and
any plugin-owned `data`. Framey sorts a copy of the entries and offers native
Move up/down, Save order and Cancel reordering actions. Saving passes a new
array with positions starting at zero to `onSave`; it does not mutate the
objects you supplied. Optional `interactables` receive `{entry}` and remain
available outside an order edit. Return an asynchronous save promise so Framey
can keep the list busy and show a rejection for retry. A handler that returns
before its backend write finishes cannot report that write's later failure.
A refreshed `entries` array replaces the old draft; late completion from the
old save cannot overwrite it. `disableReordering` hides the ordering controls
and discards an unsaved draft without calling `onSave`.
Steam animation, drag gestures and physical controller navigation are not
implemented by this control.
Treat module lookup results as Framey-local exports. Do not depend on Steam
webpack IDs, function-source signatures, or Steam-only CSS class names; a
lookup that works in the Steam Deck QAM can still return `undefined` here.
Use a local control or a visible unsupported message when it does. For a
confirmation, call `showModal` with a `ConfirmModal` and keep any irreversible
operation behind its OK action. Return an asynchronous save from `onOK`, such
as `onOK={() => saveSetting()}`, and let failures reject that promise. Framey
keeps the dialog busy until the save settles, displays an error and permits
retry after failure, and closes after success. The
[settings sample](../examples/framey-settings/README.md) tests delayed replies,
failed saves and retry through the built bundle and local modal host.
`Focusable.onActivate` accepts pointer and
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
When adapting older nested settings, `findInTree(data, filter, {walkable, ignore})`
can locate a value in the data your plugin already holds. It visits the root
first, then arrays and object keys in order, and returns the matching object.
Check for a missing match before reading a property. `findInReactTree` uses
the same search with React child keys; neither helper obtains a Steam root or
enables library-page patches. Migrate only data your plugin owns and keep
unrecognized schemas intact until you can handle them explicitly.
The Framey `localStorage` bridge is for disposable frontend caches, including
the cache read attempted by Steam Status 1.2.3. It does not expose another
plugin's cache or the Frame Control UI key. A real Steam Status panel reopen
and a worn-headset settings check are still needed. When browser storage
rejects a write, the parent panel shows a notice that its latest settings are
kept for this page only. **Retry saving** persists the current complete fallback
snapshot if storage has recovered; authors do not need to issue another edit.
The notice survives plugin close/reopen and unrelated panel status updates,
and disappears after a successful write or retry. It is scoped to the selected
plugin. Reloading or closing Frame Control before success loses that fallback.
Native browser storage retry and full-page reload readback are tested locally
with synthetic snapshots; this is not live headset persistence proof.

Register backend event listeners when a view mounts and remove the same callback
when it unmounts, using `removeEventListener(eventName, callback)`. Framey checks
the registration again before delivering each queued callback, so a callback
removed during the current event batch cannot update a retired view. Late event
replies after panel close are ignored. Local host tests cover these races with
synthetic timer events; they do not establish real-device or worn VR behavior.

HLTB for Deck 2.0.12 demonstrates the limit of the panel shim: its official
bundle can start and produce a settings view with Framey's Steam module lookup
stub, but its game page and context menu patches have no Steam target in the
isolated panel. The tests do not call its HLTB network search or Python backend.
Do not claim game length badges work in VR from this result.
