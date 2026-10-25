# Framey loader on Steam Frame

Framey is an experimental bridge for Decky store plugins inside Frame Control's
SteamVR dashboard panel. It is opt in. The panel and Decky backend are ordinary
user services under `~/.local/share/frame-control`; neither needs root or a
read-write SteamOS root filesystem. Decky's standard Quick Access menu still
does not appear in the separate SteamVR CEF target.

## Use in the headset

Install **Frame Control in VR** and **Decky Loader on Frame** from Frame Control
on your computer. Open the Frame Control tab in SteamVR, then choose **Decky
plugins → Open official store**. Search the catalogue, confirm an install, and
choose **Open panel** from the installed plugin list. The panel contains the
plugin's own controls and settings. Update and Remove affect only plugin
folders that Frame Control's store manager installed.
Removing a plugin keeps its Decky settings. Removing the Frame Control headset
panel or Decky backend keeps plugin folders until each is removed separately.

Frame Control's existing official-store manager downloads a published ZIP from
Decky's content-addressed CDN, verifies its store SHA-256 hash and manifest,
rejects unsafe ZIP members, path collisions, special files and root plugins,
and swaps one managed plugin
folder with rollback on failure. It rejects non-ARM64 ELF and Windows binaries.
The Decky user service restarts after a file change. Framey's panel host accepts
API v2 bundles and API v1 bundles using Decky's modern frontend initializer,
with `dist/index.js`. Legacy `(function (...) {...})(DFL, SP_REACT)` bundles are
also accepted: their returned initializer receives the legacy `serverAPI`, and
keyword backend calls use Decky's legacy RPC. The wrapper runs as a blob ES
module inside the same sandbox; it does not require `eval`. Other installed plugins remain manageable but have no
Framey panel. API v1 admission is a compatibility attempt, not a guarantee
that the plugin's controls work in VR. The store manager does not currently
screen a plugin's runtime network downloads.

## What the compatibility host supplies

The plugin bundle runs in an opaque-origin iframe in the Frame Control SteamVR
panel. It receives React 18.3.1, a small `DFL` panel-control shim, and the
Decky API v2 `call`/`callable` interface. Backend methods are sent by the
authenticated parent to Steam's existing `SharedJSContext` CDP client, then
through Decky's *existing* websocket connection. Framey never opens a second
Decky websocket, because Decky allows only one frontend connection. The iframe
does not receive Frame Control's UI key. React and ReactDOM are bundled for
offline use under their MIT licenses in `ui/vendor`.
Framey gives each plugin a bounded `localStorage` substitute because browser
storage is denied to an opaque-origin iframe. The parent panel keeps a separate
cache for each plugin: up to 64 keys, 64 KiB per value and 128 KiB total. It
restores the cache when a panel reopens if the parent's browser storage is
available. If storage is denied or cleared, the cache lasts only for the current
panel. Use the plugin backend for settings that must survive cache loss.

The host currently supplies sections, rows, buttons, toggles, text fields,
sliders, grouped dropdowns,
scroll containers, a modal, locale information, local panel routes and toasts,
and backend calls for the plugin that owns the panel. Steam library/store page
patches, global Steam UI components, file pickers, and privileged root methods
have no VR target. A plugin that depends on them can render only part of its UI
or show an incompatibility message. A Decky plugin's Python backend still runs as
the headset user when Decky loads it, so review third-party code before opting
in. The panel iframe can make HTTPS requests subject to ordinary browser CORS.

ProtonDB Badges' current API v2 bundle rendered its settings in a local Chromium
browser with a stubbed backend reply on 25 October 2026. Its controls accepted
pointer input. This does **not** verify SteamVR visibility, controller input,
live Decky settings persistence, or badges on Steam game pages. The last item
has no supported injection target in the Frame Control panel.
The [browser and fake Frame evidence](evidence/framey-browser-2026-10-25.md)
records exactly what was exercised.
The pinned official Steam Status 1.2.3 frontend also
[rendered in local Chromium](evidence/framey-steam-status-browser-2026-10-25.md)
with a stubbed settings reply. Its public status request worked, but its cache
logged `localStorage` errors in Framey's v0.4.34 opaque iframe. A later
[local browser check](evidence/framey-session-cache-2026-10-25.md) confirmed
that a panel-lifetime substitute avoids those errors while preserving the
opaque origin. A [second browser check](evidence/framey-cache-browser-2026-10-25.md)
tested the per-plugin cache after reopening a panel. These checks used a stub
backend and no worn headset.
Fake Frame CI also installs and removes pinned official ProtonDB Badges 1.3.4,
Steam Status 1.2.3, and Storage Cleaner 1.4.0 archives, checks their API v1/v2
manifests and frontend bytes, and verifies they can be packed as Framey panels.
It does not execute their actual backend code or prove their frontend controls
work in VR. Storage Cleaner rendered an
[empty-data panel in local Chromium](evidence/framey-api-v1-browser-2026-10-25.md).
Its cleanup actions were not tested; they may remove local game saves.

The fake Frame integration test now writes a Decky setting through Framey's
scoped backend endpoint, reads it in a new CEF request, updates the plugin,
then checks it again. It also confirms removal blocks method calls and a
reinstall can read the retained setting. This tests the bridge and fixture;
real Decky settings persistence on a worn Frame is still unverified.

The in-headset **Open official store** view loads the full official catalogue.
Search matches names, authors, and descriptions. Filters show non-root plugins
or installed plugins, and Previous/Next buttons browse 20 results per page.
The root label is a compatibility warning; other APIs are checked only when a
plugin is opened. Both `root` and `_root`
store tags mark a plugin as needing root, and duplicate store IDs are omitted
because an ID alone could select a different archive than the visible row.
The store still needs the managed Decky user service running
before its Install or Update buttons are enabled. If a plugin prevents Decky
from starting, Remove remains available for Frame Control-owned plugins while
the managed service is stopped; it does not restart the service.

Install, Update, and Remove show the current job stage in the headset panel.
The store verifies each downloaded archive and the headset applies it with a
rollback if Decky cannot start. The panel remembers the current job ID for this
browser session, so **Check result** can resume polling after a navigation or
temporary connection error. Refresh the installed list before starting another
operation after an error. The headset panel and desktop app send the hash of
the version you saw; if the official store changes that version before the job
starts, Frame Control stops before downloading or changing the headset. Refresh
the store and review the new version before retrying. If Frame Control restarts, it cannot recover the old
job result. The panel clears that job ID and asks you to refresh the installed
list before making another change.

## For plugin authors

Start with the [Framey settings sample](../examples/framey-settings/README.md)
for a buildable Decky API v2 panel and Python settings backend.

Publish a normal [Decky store](https://plugins.deckbrew.xyz/) API v2 release
with `plugin.json`, a single `dist/index.js` ESM frontend entry point, and a
Python backend if needed. Give the frontend a `content` React element returned
by `definePlugin`, and build settings as panel controls from `@decky/ui`.
Backend calls through `@decky/api` reach only that plugin's own backend.
For best VR compatibility, keep the panel self-contained and use `PanelSection`,
`PanelSectionRow`, `ButtonItem`, `ToggleField`, and `DropdownItem`. Handle a
missing Steam UI route, store overlay, or `SteamClient` object gracefully.
Avoid root, remote binary downloads, Steam library patches, and assumptions
about Steam Deck hardware. Declare settings defaults so a fresh user service
can render without pre-existing files. Test your ZIP with the store validator
and the fake Frame flow before asking users to install it.

An API v2 plugin's normal `content` is its default VR panel. Framey also shows
an optional `settings` React element under a **Settings** tab and an optional
`titleView` above it. For one-tap headset controls, return
`frameyQuickActions: [{label: 'Refresh data', onClick: refreshData}]` from the
plugin initializer. Framey displays up to eight actions and reports a pending,
success, or failure state. These descriptor fields are Framey additions; Decky
ignores them. Use a plugin backend method through `@decky/api` for work needing
persistent state, and keep a quick action safe to repeat.
See the [API v2 compatibility table](frame-plugin-author.md#framey-api-v2-compatibility)
for tested behavior and remaining limits.

The [Frame Control extension API](extensions.md) is an alternative for a
Frame-specific panel. It needs only a local manifest, HTML, and the read-only
`status` bridge; it does not need Decky.

## Removal

Use **Remove** on each installed Framey plugin, then **Remove managed Decky**
and **Remove** under Frame Control in VR. These operations remove only
Frame Control-owned folders and services. Settings, the Chromium profile, and
other users' plugins are preserved. To remove one managed plugin manually,
first inspect its `.frame-control-store.json` receipt in
`~/.local/share/frame-control/decky/plugins/<folder>`, then delete only that
folder and run `systemctl --user try-restart frame-control-decky.service`.
The Decky and headset service manual removal commands are in
[Decky on Frame](decky-frame.md#opt-in-and-remove) and
[Frame Control in the headset](headset-app.md#remove).

## Fast worn-headset check

With an already installed Framey plugin and someone wearing the headset, run
`python3 scripts/framey-worn-check.py --worn-confirmed` from a paired computer. The script
atomically acquires `/tmp/frame-test.lock` before reading battery or SteamVR
activity. If another job owns the lock, it makes no sensor reads. It releases
its own lock without starting the interaction when the headset is in standby.
Within 35 seconds, use a controller
to open a managed plugin panel and touch one setting. The script records a
fresh trusted pointer event, the panel-ready event, SteamVR overlay visibility,
and a stereo screenshot with varied pixels. It deletes its own short-lived
challenge and releases only its own lock. It records the screenshot hash and
color count, then removes the private temporary image from both devices.
Pixel variety alone cannot prove the UI text was legible; a person must still
confirm the view in the headset. The script does not install or remove a plugin,
alter Steam settings, or wake the headset.


## Unattended VR checks

The [unattended check](framey-vr-check.md) can wake, inspect and capture the
real compositor, send OpenVR mouse input, and exercise a temporary sample
against live Decky with restoration and shared-lock protection. Its
[device evidence](evidence/framey-vr-2026-10-25/README.md) distinguishes these
checks from physical controller and wearer validation. A trusted pointer event
and active-headset telemetry are both reproducible without wearing the Frame;
they must not be labelled as physical controller proof.
