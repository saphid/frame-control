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
An empty frontend entry cannot open as a Framey panel. The local archive checker
marks it as `panelCandidate: false`; a backend-only ZIP can still be installed.
Save `plugin.json` as UTF-8 JSON without a byte-order mark. Unicode names and
descriptions are supported, but UTF-16/32 and BOM-prefixed manifests are rejected
before transfer and extraction: the installed loader cannot read them. The
local archive checker enforces the same encoding rule.
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
file, and use a default when no saved setting exists.

Flush the temporary file's buffered writes and call `fsync` before replacing
the old file. On Linux, flush the settings directory entry after replacement
before acknowledging a save. The sample propagates either flush error; a
failure after replacement is uncertain and requires a fresh read, since the
new value can already be readable. Local process-exit and injected-error tests
do not prove headset power-loss durability.

Treat a damaged or unreadable saved file as an error and preserve it; returning
a default as a successful read can let the next edit erase recoverable data. The sample
rejects malformed JSON, invalid UTF-8, non-object JSON and saved non-boolean
values on both read and save. Repair or restore its `settings.json`, then
reload the saved setting before editing again.
Removing a managed plugin leaves its Decky settings behind; document how users
can reset data your plugin owns.
Keep setting mutations disabled after a failed backend read until an explicit
reload succeeds. An initial display default or a stale value is not a recovered
saved setting. The settings sample demonstrates this guard for its toggle and
Reset action, including callbacks retained before React redraws.
Validate backend replies at runtime as well as stored data. TypeScript
`callable` annotations do not validate RPC results: a resolved string or object
is not a boolean setting, and a fulfilled promise is not necessarily a save
acknowledgement. The sample accepts only boolean reads and its backend's
literal `true` save acknowledgement; invalid results leave editing locked
until a valid reload and do not announce success.
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
Keep unfinished writes ordered across view remounts as well. The sample retains
its pending save at module scope: a reopened settings view and its read-only
quick action wait for the reply, then read the saved value after either success
or failure. A retired waiting view sends no read. This prevents a pre-save
snapshot from enabling a second edit; it does not cancel backend work or
coordinate independent clients.

Give text fields a visible `label` or an explicit `aria-label`; Framey preserves
the latter on the native input. This includes Wine Cellar 0.2.1's published
installed-game search, tested with synthetic search text in the local host.
Accessible-name preservation does not prove VR keyboard or controller usability.

For numeric `TextField` controls, Framey maps Decky's `rangeMin` and `rangeMax`
to the native input's `min` and `max`. Framey also passes `maxLength`,
`minLength`, `pattern` and `required` to its native input. These four props are
explicit Framey support; `@decky/ui` 4.11.0's `TextFieldProps` does not declare
them, so authors using that type need a local input-prop extension and must
check behavior separately in Decky. Native constraints keep the original
`onChange` event, including invalid intermediate drafts and `currentTarget.validity`.
They do not cancel backend calls or clamp programmatically supplied values.
Check the draft before saving and validate it again in the backend.

Use `Field.onActivate` or `Field.onClick` for a locally actionable row. Framey
gives it a native tab stop with pointer and Enter/Space activation; `disabled`
suppresses the row's actions. `focusable={true}` also gives a row without an
action a tab stop. Ordinary fields keep their native label/input association.
These callbacks receive native React events, not Steam gamepad events; Steam
library-page navigation is still unavailable inside the isolated panel.

`Focusable` forwards React object and callback refs to its local native `div`.
Use the ref's `.focus()` for local focus management and check for `null` before
using it; React clears the ref when the control unmounts. An actionable control
has a native tab stop, while a plain container needs an explicit `tabIndex` to
receive focus. This provides DOM focus, not Steam's controller focus tree.

Set `Tabs.autoFocusContents` to move local DOM focus into the selected tab on
mount and when its ID changes. Framey chooses the first visible, enabled
sequential tab stop, or the panel itself for text-only content. A child's own
mount focus takes priority; redrawing the same tab does not interrupt editing.
Controlled tabs move focus when `activeTab` changes, rather than when a header
merely calls `onShowTab`. Omitting the option or setting it false leaves focus
under your control. This does not establish Steam controller navigation.

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
VR. The [sample plugin](../examples/framey-settings/README.md#build) uses
`scripts/framey-pack-sample.py` to package its three release files reproducibly
and run this checker before replacing the destination ZIP. It packages an
existing build; plugins with extra assets or chunks need their own packaging
step before using the checker above.
The checker reads every file through its ZIP checksum, including large assets
and backend files, before accepting the archive. A checksum error means the ZIP
must be rebuilt or recovered from its source; it is not a frontend compatibility
verdict. The store runs this same validation before transfer to the headset.

For an API v1 bundle whose Decky initializer is in `dist/chunks`, keep direct
children with a `.js` suffix as files. A directory named `helpers.js` (including
one implied by `helpers.js/data.json`) makes the runtime reject the panel.
A file named only `.js` has no suffix and cannot supply that initializer;
ordinary chunk files such as `entry.js` or `.bridge.js` can. The local checker
applies the same admission rules; it does not execute the frontend.

The checker rejects a file used as a directory or parent path: do not include
both `your-plugin/dist` as a file and `your-plugin/dist/index.js`. It also rejects
a file and directory with the same path even when the directory entry ends in
`/`. Ordinary explicit directory entries can appear before or after their files,
and ZIPs that omit directory entries are accepted. This validation runs before
the store sends an archive to the headset and again before remote extraction.

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
| `SliderField.icon` | Preserves the plugin's React icon beside the label and description, including disabled sliders. Removing the icon removes its content. | Exact RadiYo! 1.3 volume control and published speaker SVG runtime in real React/DOM with synthetic volume state: numeric changes, disabled callbacks, icon props and removal. No playback, backend, settings save, controller or worn VR proof. |
| `SliderField.className` | Applies the supplied CSS classes to the local field wrapper, containing its label, description, range and optional actions. Class updates and removal follow the current props. | Exact SteamGridDB 1.8.1 size-slider expression, numeric limits and toolbar CSS rule in real React/DOM with local zoom state: computed flex/padding, numeric callback, disabled suppression, class replacement/removal and field content. No artwork search/change, saved settings, backend, controller or worn VR proof. |
| `SliderField.notchLabels`, `notchCount` | Shows the supplied captions in a local grid and exposes the caption matching the current value as `aria-valuetext`. Numeric callbacks still return the slider value. | Exact Steam Status 1.2.3 refresh-interval control in real React/DOM with synthetic settings: minute captions, numeric seconds and disabled state. No backend, live refresh, controller or worn VR proof. |
| `SliderField.notchTicksVisible` | Explicit `true` shows evenly spaced decorative marks beneath the native range for a valid `notchCount` from 2 through 100 and finite increasing bounds. False or omitted hides marks while retaining captions. Marks do not add focus targets, snap values or change validation. | Exact SteamGridDB 1.8.1 artwork-size slider and configuration in real React/DOM with synthetic size state: hero/logo tick counts, visible geometry, updates, disabled callbacks, captions and invalid bounds/counts. No artwork changes, saved settings, backend, physical controller or worn VR proof. |
| `ToggleField.tooltip` | Shows the plugin's help as visible text below its toggle, including when disabled, without requiring hover. Existing descriptions and React help content remain available; omitted help adds nothing. | Exact Pause Games 1.0.3 suspend/overlay controls in real React/DOM with synthetic settings writes: help visibility, true/false callbacks and disabled suppression, plus React content, text escaping and removal checks. No app pause, suspend, backend, saved settings, physical input or worn VR proof. |
| `Field.icon`, `ToggleField.icon`, `ButtonItem.icon` | Keeps the plugin's React icon beside the field label, including its supplied SVG geometry, title, class and style. | Exact Simple Timer 1.0.0 Subtle Mode toggle and speaker icon in real React/DOM with a synthetic save callback; enabled/disabled transitions, plus local Field/ButtonItem icon fixtures. No timer backend, audio playback, controller or worn VR proof. |
| `ButtonItem.style` | Applies the supplied style to the local field containing the label, description, icon and native button. Removing the prop removes the old style; disabled buttons keep their appearance and suppress clicks. | Exact Deck Progress Tracker 1.3.6 game button and width/overflow styles in real React/DOM with navigation recorded locally, plus hidden-field and style-removal fixtures. No Steam navigation, backend, controller or worn VR proof. |
| `Field.onActivate`, `onClick`, `focusable`, `className` | Action rows use a local focus target with native click/Enter/Space activation and disabled suppression. `focusable` adds a tab stop without requiring an action. Classes, styles, label, description, icon and children are retained. Ordinary setting rows keep their native labels. | Exact Emuchievements 2.0.5 achievement row in real React/DOM with synthetic progress and navigation callbacks; updated/disabled actions, original events, local focus and ordinary toggle-label behavior. No achievement service, real Steam navigation, backend, physical input or worn VR proof. |
| `PanelSection.spinner` | Shows a local loading status and marks the section busy while true, retaining its title and children. It does not disable child controls; the plugin still owns their disabled state. | Exact Virtual Surround Sound 0.0.5 loading section and Storage Cleaner 1.4.0 section header/condition in real React/DOM with synthetic state: loading, known empty data, populated data, updates and child callbacks. No real settings read, cache read/removal, audio, controller or worn VR proof. |
| `Dropdown.onMenuWillOpen(showMenu)` | A Load options action invokes the plugin's loader. Choices become selectable only after `showMenu()`; Reload options invokes it again. Cancel loading hides the wait and rejects late callbacks. | Exact published Wine Cellar 0.2.1 option-loader callback with synthetic tool replies; host contract tests. No live helper or worn VR check. |
| `Dropdown.renderButtonValue` | Renders a plugin-supplied current-value view above the native select or deferred loader. Receives the matching option's label, or the default label when no choice matches; the original option object still reaches `onChange`. | Exact published Wine Cellar 0.2.1 renderer/control in real React/DOM with synthetic tool choices: initial/loading/updated/disabled values, styles, accessible label and empty-string selection. No real tool discovery/assignment, backend or worn VR proof. |
| Nested `Dropdown.rgOptions` groups | Recursively lists selectable leaves in source order. Native selects show each contiguous group run under its full text path, such as `Outer › Inner`; group headers and empty groups are not options. Selection, `onChange` and `renderButtonValue` resolve the original leaf object/label, including zero, empty-string and undefined data. | Published Wine Cellar 0.2.1 control replay with synthetic nested choices shaped by `@decky/ui`'s recursive option type: deep selection, callback identity, group paths, reordered/reloaded choices, disabled suppression and label rendering. This does not show that Wine Cellar itself produces nested groups, or prove real tool discovery/assignment, backend or worn VR use. |
| `TextField.defaultValue`, `onBlur`, `onFocus`, `onClick`, `onKeyDown`, `onKeyUp` | Uncontrolled input drafts and original React events reach the plugin callbacks; disabled fields suppress callbacks. A controlled `value` takes precedence over `defaultValue`. | Local host contracts and the exact Game Sync 1.0.4 text-dialog function: edited draft/OK and Cancel. No sync, backend, real input device or VR keyboard check. |
| `TextField.rangeMin`, `rangeMax`; explicit Framey support for `maxLength`, `minLength`, `pattern`, `required` | Native input constraints and validity; invalid drafts still reach the plugin's original change handler. Changing or removing props updates the same input. Plugins own save validation. | Real React/DOM with synthetic controlled/uncontrolled drafts: maximum-length editing, minimum-length attribute, required/pattern and numeric-bound validity, clear action, disabled callbacks, prop removal and stable refs. Synthetic editing does not establish minimum-length validity for physical input. No backend, controller or VR keyboard proof. |
| `TextField.focusOnMount` | Focuses an enabled native input when it mounts. A modal preserves focus already inside it, falling back to its shell when nothing inside has focus. Updating an existing field does not refocus it. | Exact RadiYo! 1.3 text dialog in real React/DOM with synthetic query input; opt-out, disabled, update, shell fallback and focus restoration checks. No radio backend, physical controller or VR keyboard proof. |
| `TextField` refs | Object and callback refs receive a local handle with `.element` pointing to the native input and `Focus()` using its native focus. Ordinary redraws preserve the handle; ref replacement and unmount detach the old ref. Retained handles expose a null element after unmount. Disabled inputs cannot receive focus. | Exact TabMaster 2.15.1 search control and SELECT handler in real React/DOM with explicitly synthetic event detail. Query editing, native focus/blur, callback replacement, cleanup and module lookup checked. No Steam library changes, backend, physical controller, worn visibility or VR keyboard proof. |
| `TextField.bShowClearAction`, `bAlwaysShowClearAction` | An opt-in Clear button empties the input through its native React change event. It hides when empty unless always-visible is requested; disabled fields stay inert. | Pinned Wine Cellar 0.2.1 search-control fixture; automated React/DOM check requires Linux Chrome. Worn VR remains unverified. |
| `TextField.inlineControls` | Renders the plugin's supplied React controls after the input and built-in actions. Supplied controls retain their own callbacks, styles and disabled state. | Exact Web Browser 1.4.3 favorite-folder component in real React/DOM with an in-memory favorites stub: empty-name disabled action, edited draft/parent path, existing-folder guard and nested-dialog callback. No real favorites, browser tabs, backend, physical input or VR keyboard proof. |
| `Field.style`, `TextField.style` | Applies the plugin's React style object to the native field wrapper, including its description and built-in actions. Styles update with the current props. | Exact DeckyFileServer 1.2.0 port control in real React/DOM with synthetic port state: red validation border, dimensions, callback and border removal. A local fixture also checks hidden fields/actions and ordinary unstyled fields. No server, settings save, physical input or VR keyboard proof. |
| Scrollable panel content | Visible Scroll plugin up/down buttons move the last region reached by a trusted pointer, or the document if that region disappears. Hold either button to repeat; keyboard activation still moves one step. Plugins may use ordinary CSS overflow containers. | Parent/iframe message tests and a real Frame synthetic OpenVR pointer hold; physical controller scroll and hold remain unverified |
| `ScrollPanel`, `ScrollPanelGroup` refs | Object and callback refs receive the local native div, exposing `scrollHeight`, `clientHeight` and `scrollTop`. Props, children and the node persist across ordinary redraws; ref replacement and unmount detach old refs. Plugins supply their viewport dimensions and overflow CSS. | Exact TabMaster 2.15.1 ref, overflow effect and panel expression in real React/DOM inside a synthetic bounded viewport; changing content, native scroll position, both containers, ref replacement/cleanup, child actions and local module lookup. No full TabMaster modal/layout, library, backend, physical input or worn VR proof. |
| `Tabs`, `SidebarNavigation`, spinners, dialog/menu wrappers | Local tab navigation and ordinary HTML controls; no Steam navigation or controller focus tree | Host tests and catalog frontend smoke checks in local Chromium |
| `Tabs` entries with `renderTabAddon` | Calls each tab's renderer beside its title on every render, retaining returned React markup and zero counts. Controlled/uncontrolled selection and disabled tabs keep their existing behavior. | Exact Animation Changer 1.3.2 tab expression in real React/DOM with synthetic browse/installed arrays; counts update without changing selection. Child views are inert; no animation discovery/download, full plugin, backend, controller or worn VR proof. |
| `Spinner.style`, `SteamSpinner.style` | Preserves the supplied React style object on the loading status, including visibility and positioning; removing the style restores the ordinary status. Custom React children and the default loading message remain available. | Exact RadiYo! 1.3 overlay style and spinner expression in real React/DOM with synthetic playing/buffering/paused states, plus style removal and SteamSpinner alias checks. No player, station, audio, backend, physical input or worn VR proof. |
| `Menu.label`, `cancelText` | Renders a visible heading. A direct root `Menu` also gives its local dialog the string label as an accessible name and uses nonblank string `cancelText` for its shell cancel button (default Close). Existing cancellation/disabled guards apply. | Exact MusicControl 1.1.6 provider-menu handler in real React/DOM with synthetic providers: heading, accessible name, Cancel text and unchanged provider callbacks; local cancellation, Hide/Show, updates and fallbacks. No player/backend, saved settings, controller or worn VR proof. |
| `MenuGroup.label`, `disabled` | A labeled native fieldset; disabling it blocks native activation and focus of descendant controls, including nested groups. Individual `MenuItem` disabled states still apply. | Exact TabMaster 2.15.1 Micro SD Card menu with synthetic cards/preset callbacks in real React/DOM. No card discovery, real library edit, Steam submenu or worn/controller proof. |
| `MenuItem.selected` | When supplied, exposes selection through `aria-pressed` on the native button and a visible checkmark. An absent selection prop leaves ordinary action semantics. The plugin owns selection updates; disabled selected items remain inert. | Exact TabMaster 2.15.1 custom-dropdown menu factory in real React/DOM with synthetic choices: original option identity, updated selection on reopen, missing selection, disabled actions and prop removal. No real settings/library mutation, backend, physical input or worn VR proof. |
| `SidebarNavigation.pages` with `"separator"` entries | Omits layout separators from the local tab strip so they cannot open blank pages. Hidden pages stay absent; changing visibility of an earlier page preserves a later page's selection at the same source index. | Exact published Game Sync 1.0.4 navigation replay with inert child views and synthetic tab selection. No sync, backend, physical-input or worn VR proof. |
| `ReorderableList` | Lists plugin entries by `position`; native Move up/down buttons edit a draft. Save order calls `onSave` with normalized positions; Cancel discards the draft. Labels, data and optional `interactables` are retained. `disableReordering` hides ordering controls. | Exact published TabMaster 2.15.1 list/save callback with synthetic entries; cancel, disabled/late handlers, failed-save retry and refreshed-list tests. No real library edit or physical controller check. |
| `ProgressBar`, `ProgressBarItem`, `ProgressBarWithInfo` | Native progress control; `indeterminate` or an absent progress value omits the native value so it animates as unfinished. Numeric zero remains determinate. Item and WithInfo preserve React `label` and `description` content, and WithInfo shows `sOperationText`. Estimated completion time is not shown. | Exact Emuchievements 2.0.5 progress expressions and SuggestMe 1.5.3 refresh-progress expression in real React/DOM with synthetic errors, counts and totals. Description/markup updates, unknown-to-known totals, numeric zero, completion and return to unknown verified. No achievement/refresh service, live backend, controller or worn VR proof. |
| `SteamUIStore` / `DFL.Router.RunningApps`, `MainRunningApp` | Bounded detached Steam CEF reads while the panel is open; refresh about every two seconds; no MobX observation. Failed reads clear stale context. | Locked real Frame empty-list reads; nonempty local Chromium fixtures. Real running-game selection unverified. |
| `GameSessions.RegisterForAppLifetimeNotifications` | Actual Steam callbacks, bounded queue and disposable `.unregister()` handle; no events inferred from snapshot changes; lease cleanup after lost panels | Real Frame registration/poll/close; launch/exit, retry, expiry and duplicate tests use explicit fixtures. Real game transitions unverified. |
| Other `SteamClient` subscriptions | Explicit inert registration methods return disposable handles; no fabricated power/input/game-action events. Mutating Steam/power methods are unavailable. | Host contract tests; safe fallbacks only |
| `DialogCheckbox`, `DialogButtonPrimary` | Native checkbox and button controls in the panel. Checkbox wrapper classes/styles are preserved; `onClick` receives the native input's React event, while `onChange` receives its checked boolean. Disabled inputs suppress both. | Host unit test; exact SteamGridDB 1.8.1 multiselect item and published pointer-routing CSS in real React/DOM with synthetic filter selection. No artwork, backend, controller or worn VR proof. |
| `Button` | Renders a native button without a field wrapper, preserving React children, classes and styles. Uses `onClick` first, otherwise `onOKButton`; disabled controls suppress activation and do not submit enclosing forms. `ButtonItem` remains a labeled field with a button. | Exact Simple Timer 1.0.0 minute-button component in real React/DOM with synthetic callbacks: layout, enabled/disabled colors, callback priority, OK fallback, original event, form behavior and style removal. No timer, backend, settings save, physical input or worn VR proof. |
| `DialogButton`, `DialogButtonPrimary`, `DialogButtonSecondary` with `onOKButton` | Native activation calls `onClick` when present, otherwise `onOKButton`, once. The callback receives the original React click event, not a Steam `GamepadEvent`. Disabled buttons stay inert; buttons do not submit an enclosing form. Classes, styles and other native props are retained. | Exact SteamGridDB 1.8.1 tab-settings actions in real React/DOM with synthetic callbacks: default tab, hide/show and last-visible-tab guard. All three variants, callback priority and disabled behavior checked. No saved settings, artwork, backend, controller or worn VR proof. |
| Optional `settings`, `frameyQuickActions` | Separate settings tab when content also exists; settings-only plugins have no empty Panel tab; up to eight actions with result text | Host unit test; these fields are Framey additions |
| `serverAPI.call` / `callable` | Calls only that plugin's Decky Python backend via the headset service | Fake Frame e2e; real ARM64 Notebook save/reopen across backend restart and Simple Timer settings/recents persistence via local Chromium. No worn-VR claim. |
| API v1/v2 `addEventListener` / `removeEventListener` | Plugin-scoped real backend events while panel is open; bounded queue, about one-second polling, subscription expiry | Real ARM64 Simple Timer countdown, start/cancel and completion toast via local Chromium; scope/bounds/reconnect tests. No closed-panel notifications. |
| `toaster.toast` | Visible toast inside the plugin panel; plain text or React nodes for title, body, icon, logo and subtext; `dismiss` and optional `onClick` | Host unit test; no Steam system notification or worn VR check |
| `Focusable` refs | Forwards object and callback refs to the native container; `.focus()` uses local DOM focus. Ref replacement and unmount detach the old ref. Native click/Enter/Space activation and disabled suppression remain available. | Exact SuggestMe 1.5.3 Back control and focus effect in real React/DOM, with a synthetic navigation callback; focus/blur styling, spacer opt-out, callback ref replacement and passive container checks. No recommendation service, backend, physical input or worn VR proof. |
| `Tabs.autoFocusContents` | Opt-in local focus moves into selected content on mount or a changed tab ID. Disabled, hidden and negative-tabindex controls are skipped; text-only content focuses its panel. A child's mount focus and same-tab editing focus are preserved. | Exact Game Theme Music 1.7.1-1 Tabs expression with synthetic pages in real React/DOM. Initial/switch/return focus, controlled selection, disabled header, fallback panel, opt-out, ineligible targets and field mount focus checked. No music service, backend, controller or worn VR proof. |
| `localStorage` | Synchronous, per-plugin cache backed by the Frame Control panel origin. Up to 64 keys, 64 KiB per value and 128 KiB total; `clear()` removes only this plugin's cache. Failed writes stay in parent-page memory across plugin reopen until a write succeeds. Reloading that page loses the fallback and may restore older disk values. Plugin code waits for the cache reply. A failed browser-storage read or invalid saved snapshot stops startup immediately and preserves the saved bytes; reopen after access recovers, and recover invalid data separately. A valid in-memory fallback still works when disk reads are blocked. Only an absent cache starts empty; a missing reply fails after five seconds. | Parent/iframe round-trip, delayed reply, timeout, denied/quota-exceeded writes, plugin isolation, storage recovery and reopen in the local host test; native browser read-denial/corruption preservation and recovery fixtures. Real headset persistence remains unverified. |
| `localStorage.name`, `localStorage['name']`, `delete localStorage.name` | Direct string-property writes, reads and deletion use the same bounded snapshot as `setItem`, `getItem` and `removeItem`. Values become strings, including empty strings and zero; a missing property is `undefined`. `Object.keys`, `Object.entries`, object spread, `for...in` and JSON serialization expose saved non-reserved names and values; API methods and `length` are not enumerable. API/prototype members remain available; use `getItem` and `length`/`key(index)` for saved keys with those reserved names, which are omitted from named enumeration. | Real parent/iframe scripts with synthetic storage: export and reopen, own descriptors, empty/numeric names, method/property interoperability, deletion/clear, plugin isolation, quota rejection and denied-write fallback/recovery. No live-headset persistence proof. |
| `SteamClient.Storage.GetJSON` / `SetObject` | Uses the same bounded per-plugin cache; a missing key rejects with `Not found`. It cannot read Steam account or global storage. | Host contract tests and local Chromium settings views; headset persistence after reopen remains unverified. |
| IndexedDB / localForage | IndexedDB is deliberately absent inside the opaque iframe so feature detection chooses the bounded localStorage driver. Plugins requiring IndexedDB directly remain unsupported. | HLTB official frontend in local Chromium: its previous `IDBFactory.open` SecurityError disappeared. No live HLTB data request was run. |
| `routerHook.addRoute` / `removeRoute`, `Navigation.Navigate` / `NavigateBack`, `useParams` | Local routes inside this plugin panel, with named segments such as `/plugin/game/:appid/:view?`; `useParams()` reads the current segment values. Back walks up to 32 local page transitions and skips routes removed since navigation. | Host unit test; VR navigation unverified |
| `routerHook.addPatch`, global components | No-op; cannot patch Steam routes | Not applicable |
| `findModule`, `findModuleChild`, `findModuleExport`, class lookup and module mapping | Searches a finite registry of Framey controls and CSS maps. Unknown Steam modules return `undefined` or an empty mapping. The optional UI-audio export cannot play sound. | Host contract tests; pinned TabMaster 2.15.1 QAM and documentation render in local Chromium. Steam library editing and worn VR remain unverified. |
| `findInTree`, `findInReactTree` | Searches objects and arrays supplied by the plugin, returning the first matching object. `walkable` restricts object keys and `ignore` skips them; React search follows only `props`, `children`, `child` and `sibling`. Cycles terminate. `getReactRoot()` still returns `null`. | Exact published Emuchievements 2.0.5 settings migration and reopen with synthetic legacy RPC replies; nested values, including empty strings, survive. No real account, backend, Steam-tree access or worn VR proof. |
| `Navigation.CloseSideMenus` | Returns to this plugin's main panel | Pinned HLTB for Deck 2.0.12 shallow settings view in local host test. Live HLTB search remains unverified. |
| `QuickAccessTab`, `Navigation.OpenQuickAccessMenu(QuickAccessTab.Decky)` | Legacy numeric tab identifiers and reverse lookup; the explicit Decky tab (999) returns from a local route to this plugin's current main view and clears local route history. Other tabs, omitted tabs and non-numeric values throw an unavailable error. The `Router` alias shares this mapping. It cannot open Steam's Quick Access Menu or another plugin. | Exact RadiYo! 1.3 search-dialog continuation and Free Loader 1.6.0 toast/Open callback in real React/DOM with synthetic data; route return, history clearing, enum values and unsupported tabs checked. No radio search, deals, settings save, physical controller or worn VR proof. |
| `GamepadButton` enum | Numeric button identifiers and reverse-name lookup matching `@decky/ui` 4.16.0. This exports constants only; it does not deliver gamepad events or add a Steam controller focus tree. | Exact Wine Cellar 0.2.1 paging handler/action map with directly supplied synthetic detail objects: distinct left/right keys, repeat/boundary guards and reverse lookup. Native React click events stay unchanged. No physical-controller event, real paging, backend or worn VR proof. |
| `Focusable.onActivate`, `showModal`, `ConfirmModal` | Pointer and Enter/Space activation, disabled state, and local confirmation dialogs with cancel/close and nested-dialog focus | Host tests and official AlarMe 1.6.3 timer/preset controls with a real ARM64 backend in local Chromium. Sound, suspend and worn VR remain unverified. |
| `showModal(element, parent, {fnOnClose})` | Notifies the plugin once after actual dismissal, including the handle's `Close`, shell Close/Escape and injected `closeModal`. Updating content keeps the original notification; blocked cancellation sends none. `ClosedPromise` resolves and dismissal completes even if the notification throws or returns a rejected promise; the error is displayed in the panel. | Exact SuggestMe 1.5.3 modal helper in real React/DOM, plus local lifecycle fixtures for all close paths, updates, pending confirmation, nested dialogs, reentry and error recovery. SuggestMe's no-argument Steam QAM return remains unavailable and reports an error after closing; its opt-out branch closes normally. No full plugin, backend, Steam navigation, physical input or worn VR proof. |
| `ConfirmModal` action lifetime | Closed or unmounted confirmations ignore retained OK/Cancel/middle handlers. Successful actions stay retired; synchronous reentry and pending repeats are suppressed. Failures remain visible and retryable. Unmounting a pending confirmation releases its shell's busy state and ignores its late result. | Exact Free Loader 1.6.0 clear-confirmation expression with inert backend callbacks in real React/DOM; dismissal, cancellation, completion, component replacement, synchronous reentry and synchronous/asynchronous retry checked. No database, backend, controller or worn VR proof. |
| `showContextMenu(...).Hide()` / `.Show()` | Opens a local dialog shell. Hide dismisses only that menu; Show remounts dismissed content and does nothing while visible. The instance retains its original focus target. | Exact TabMaster 2.15.1 menu factory/Hide callback with an inert library view; real React/DOM reopen, focus and nested-dialog checks. No real library edit, Steam popup or worn/controller proof. |
| `ColorPickerModal` | Local hue, saturation, lightness and alpha sliders with a preview. Defaults initialise the draft; OK passes an `hsla(...)` string to `onConfirm`. Cancel/Close discards it. A returned promise disables editing until success or a visible retryable failure. | Exact published CSS Loader 2.1.3 picker/callback replay with a synthetic setter, including draft/cancel, stale callbacks and async retry. No theme, Steam, backend or worn VR proof. |
| `SimpleModal` | Local content wrapper within `showModal`. `active={false}` unmounts its children; true or omitted renders them. The existing shell owns focus and dismissal. | Exact Web Browser 1.4.3 warning replay, including accept and shell cancellation; real React/DOM checks child styles, focus restoration and inactive-child cleanup/remount. No full Web Browser/DeckSP, Steam portal, backend, controller or worn VR proof. |
| `ControlsList` | A wrapping row of plugin-supplied controls. `alignItems` places them left (default), center or right; `spacing` uses 8px (standard) or 16px (extra) gaps. Children keep their callbacks, styles and disabled state. | Exact SteamGridDB 1.8.1 informational modal/footer in real React/DOM: renders and closes with focus restored. Separate layout checks cover alignment, spacing and child actions. External links are never invoked; no backend, saved settings, artwork, controller or worn VR proof. |
| `ModalRoot.onOK` | An explicit local OK button calls the handler; `bOKDisabled` disables it. The handler owns dismissal through `closeModal`. Overlapping submissions, including synchronous reentry, are suppressed. Returned promises block that dialog's Close/Escape; failures remain visible for retry. Closing or unmounting retires the root's actions and late results; removing a pending root releases its shell. An open root can submit again after success. Roots without `onOK` add no button. | Exact RadiYo! 1.3 text-dialog replay and real React/DOM lifecycle fixtures with synthetic callbacks. Radio search, playback, headset settings persistence, VR keyboard, physical controllers and worn visibility unverified. |
| Custom `ModalRoot.onCancel`, `onEscKeypress` | A custom dialog that passes its injected `closeModal` to `ModalRoot` binds those handlers to its own shell. Close calls `onCancel`; Escape uses `onEscKeypress` when present, otherwise cancels. Updated or unmounted roots retire their old handlers. | Exact Decky Localsend 0.4.5 receive dialog in real React/DOM, recording synthetic decisions only. No real offer, backend, file transfer or worn VR proof. |
| Custom `ModalRoot.bCancelDisabled` | An inner root bound through its injected `closeModal` disables shell Close and default Escape cancellation, including `Focusable.onCancel`. Changing or removing the flag updates the shell; unmounting the root retires it. An explicit `onEscKeypress` still owns Escape, and programmatic `Close()` remains available. | Synthetic API-contract cases alongside the published LocalSend cancellation replay in real React/DOM: retained Close handler, flag changes/removal, root replacement/cleanup and independent parent/child flags. These cancel-disable props are synthetic; no LocalSend feature, physical input or worn VR claim. |
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

Pass a `Menu` directly to `showContextMenu` or `showModal` to use its `label`
as the shell's accessible name and its `cancelText` on the shell cancel button.
Blank or omitted cancel text uses Close. The visible heading also renders when
a `Menu` is nested, but nested metadata does not configure the surrounding shell.
Shell cancellation calls `onCancel`; item selection still belongs to the plugin.

Keep the instance returned by `showContextMenu` when a menu action needs to call
`Hide()`. Hiding is programmatic dismissal and does not invent a cancellation
result. `Show()` reopens the same element with fresh component state after Hide,
shell Close or Escape; it cannot duplicate a menu already open. Focus returns
to the original opener when it still exists and no other dialog remains open.
Menu actions do not automatically dismiss the menu, so plugins can keep
interactive choices open. Steam popup positioning, `bRetainOnHide`, submenus and
controller navigation are not implemented by this local handle.

Use `showModal`'s third argument `{fnOnClose}` for a notification after the
dialog closes. It receives no result or reason, and programmatic `Close()`
also calls it. Use `onOK` and `onCancel` to record the user's choice instead.
A promise returned by `fnOnClose` does not delay `ClosedPromise` or keep the
dialog open; put an awaited save in `ConfirmModal.onOK`. Notification failures
appear in the panel after dismissal rather than preventing cleanup.

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

For labeled sliders, supply `notchCount` (2–100) and `notchLabels` entries with
zero-based `notchIndex` and string `label`. Captions occupy their declared
positions even when some notches have no label. Each caption matches the value
evenly spaced between `min` and `max`, unless its optional numeric `value`
overrides that match. An unmatched current value keeps its ordinary numeric
accessibility value. Labels remain visible when `notchTicksVisible` is false;
Framey does not draw Steam's tick marks or add snapping beyond the native
slider's `step`.

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
Confirmation actions belong to that mounted dialog. After dismissal, unmount
or a successful action, a retained button handler cannot submit again. A failed
action can retry while the confirmation remains open. If you replace a pending
confirmation with another component, its late reply cannot dismiss or lock
that replacement. This retires the UI callbacks; closing or replacing a dialog
does not cancel a backend request already sent. Re-read saved state before
assuming what that request changed.
`Focusable.onActivate` accepts pointer and
Enter/Space input in Framey, but only a worn-headset test can establish how a
physical controller reaches it. `Focusable.onCancel` receives the original React
keyboard event for Escape from the control or its descendants. The nearest
handler consumes it and owns dismissal; call the dialog's injected `closeModal`
when it should close. Disabled controls and busy or cancel-disabled dialog shells
do not invoke it, and an `onKeyDown` handler can consume Escape first. This is a
native keyboard mapping, not proof of physical controller cancellation. The
published Web Browser 1.4.3 QR wrapper is replayed in local React/DOM with an inert
QR renderer; no external navigation or plugin service runs. See the
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
