# Framey loader on Steam Frame

Framey is an experimental bridge for Decky store plugins inside Frame Control's
SteamVR dashboard panel. It is opt in. The panel and Decky backend are ordinary
user services under `~/.local/share/frame-control`; neither needs root or a
read-write SteamOS root filesystem. Decky's standard Quick Access menu still
does not appear in the separate SteamVR CEF target.

See the [complete official-store compatibility table](framey-compatibility.md) for version-specific statuses, blockers and verification limits. Both stores and installed panels show the same digest-scoped results; a new published archive starts unverified.

## Use in the headset

Install **Frame Control in VR** and **Decky Loader on Frame** from Frame Control
on your computer. Open the Frame Control tab in SteamVR, then choose **Decky
plugins → Open official store**. Search the catalogue, confirm an install, and
choose **Open panel** from the installed plugin list. The panel contains the
plugin's own controls and settings. Update and Remove affect only plugin
folders that Frame Control's store manager installed.
Use **Scroll plugin up** and **Scroll plugin down** above an open panel when
wheel scrolling is unavailable. Point at a scrollable part of the plugin first
to move that section; otherwise the buttons move the panel document. Each
press moves about three quarters of the visible section and stops at its edge.
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

Decky API v1/v2 `addEventListener` and `removeEventListener` receive real backend
events while the panel is open. The parent resolves the plugin name from its
installed store receipt, polls Steam's existing Decky event connection, and sends
only subscribed events to that panel session. A subscription is established
before a backend call can emit its response. The bridge allows 32 event names,
queues at most 64 events and 48 KiB, and drops any event whose arguments exceed
8 KiB. Polling occurs about once a second, so this is unsuitable for high-rate
input/audio streams. Closing/reopening a panel removes its subscriptions;
abandoned CEF subscriptions expire after 15 seconds. This does not deliver
global notifications while a Framey panel is closed.

The [26 October live checks](evidence/framey-events-backend-2026-10-26.json)
used the actual official Notebook and Simple Timer Python backends in a private
removable ARM64 Decky service. Notebook's default notebook saved a pointer stroke
and loaded it after a backend restart. Simple Timer's start/cancel controls,
countdown, completion toast and persisted recents/subtle mode worked. The
[Simple Timer lifecycle repair](evidence/framey-simple-timer-2026-10-26.md) now
fixes cancellation, replacement and active/canceled/expired backend restarts,
verified through actual Decky 3.3.0 on amd64 and the ARM64 Frame. Managed
update/reinstall is required. Silent in-panel session timers qualify as works;
sound/suspend are unsupported, alerts require an open panel, and worn VR remains
unverified.

DFL module and class lookup searches a finite registry of Framey's own controls,
CSS maps and an explicitly unsupported optional UI-audio player. It follows DFL's
module/export filter and mapping contracts; unknown Steam modules return
`undefined`, and unknown module mappings are empty. Returned IDs describe local
Framey exports, not Steam webpack IDs. Sound playback throws an unsupported
error, and Steam audio stores, function-source signatures and global patches are
not fabricated. The [module lookup checks](evidence/framey-module-lookup-2026-10-26.md)
record the resulting TabMaster documentation support and remaining blockers.

The host currently supplies sections, rows, buttons, toggles, text fields,
sliders, grouped dropdowns,
scroll containers, a modal, locale information, local panel routes and toasts,
and backend calls for the plugin that owns the panel. The headset's scroll
buttons send only a direction to the isolated iframe. They target the last
scrollable region reached by a trusted pointer move and fall back to the iframe
document when that region disappears. A result message reports whether content
moved; this bridge has no backend or Steam privilege. Steam library/store page
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

Framey also supplies local tabs/sidebar pages, spinners, dialog/menu wrappers
and progress bars. Its explicit SteamClient subscription fallbacks return
disposable handles without emitting fabricated events. Running-game reads and
lifetime notifications use the scoped bridge described below; power, app launch
and hardware mutation methods are not supplied. Other live Steam stores require integration
work. IndexedDB is hidden because the browser exposes it but denies access in
an opaque iframe; localForage can then select Framey's bounded localStorage.
Direct IndexedDB users remain unsupported.

`SuspensefulImage` renders a native image. SteamClient `Storage.GetJSON` and
`SetObject` use the same bounded per-plugin cache, including panel reopen
persistence; they do not read Steam's account/global JSON store. Missing keys
reject with `Not found`. The suspend store has no methods. Optional Steam app/account globals
are undefined until a successful library read. These fallbacks let settings render without inventing live
games or account identity. [The exact-bundle follow-up](evidence/framey-ui-fallbacks-2026-10-26.json)
verifies Pause Games and Tailscale Control settings in local Chromium; their
primary backend actions remain unverified. PlayTime still requires Steam's
MobX game observers for automatic tracking.

Panels referencing running-game APIs now receive a detached, read-only
`SteamUIStore.RunningApps` / `MainRunningApp` snapshot, also exposed through
`DFL.Router`. The authenticated headset-only `/api/framey/running` endpoint
checks installed store ownership; the parent checks the active panel session.
Poll and close requests also carry the panel's pinned SHA-256 receipt. A missing
or changed installed receipt is rejected before any Steam CEF request; a rejected
stale close relies on the existing finite subscription lease for cleanup.
Fixed bundled code runs in Steam CEF. It copies at most 64 running app overviews, a main app and
public Steam CDN capsule URLs; it never copies local artwork paths, launch
commands or Steam objects. The host refreshes about every two seconds without
overlapping requests. Failure clears stale context and sets
`SteamUIStore.FrameyRunningAvailable` to false.

`GameSessions.RegisterForAppLifetimeNotifications` relays actual Steam
`{unAppID, bRunning}` callbacks through a bounded 64-event queue. Snapshot
changes never fabricate launch/exit callbacks. Handles support `.unregister()`;
panel close/replacement removes the CEF subscription, with a 15-second lease
(checked every five seconds) if cleanup cannot reach Steam. At most four panel
sessions are retained. These are open-panel observations, not closed-panel
automation or a MobX implementation. Queue overflow can lose old callbacks.
`appStore` capsule helpers expose only projected public URLs for running apps;
unavailable or local custom artwork returns an empty value.

[Running-context evidence](evidence/framey-running-context-2026-10-26.md) separates
real Frame empty-list/subscription/cleanup reads, the exact Discord Status
ARM64 backend connection check, and synthetic nonempty/transition fixtures.
Real game transitions, Discord activity and worn-VR operation remain unverified.

Three parameterless SteamClient reads use Steam's actual CEF context:
`User.GetIPCountry`, `InstallFolder.GetInstallFolders` and `System.GetSystemInfo`.
The authenticated headset-only endpoint checks that the plugin is installed,
selects an expression from a fixed allowlist, and caps replies at 256 KiB.
The iframe cannot supply a Steam property path or executable source, and replies
are discarded if the panel session changed. Unsupported APIs remain unavailable.
[Locked Frame checks](evidence/framey-steam-reads-2026-10-26.json) verified all
three reads and IsThereAnyDeal's country dropdown in local Chromium. Its backend
settings/deal calls stayed denied; Deck Settings still needs real Steam library
context. A deployed headset HTTP endpoint and worn-VR behavior remain unverified.

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
rollback if Decky cannot start. The panel saves a random request ID before
submitting a change. The server uses that ID as the job ID and returns the
same job for a repeated, identical request while its result is retained;
reusing the ID for a different change is rejected. **Check result** can resume
polling even if the POST response is lost. After a connection error, Install, Update, and Remove
stay disabled while the saved job's result is unknown; use **Check result**
before starting another change.
If Chromium denies session storage, the open panel keeps the request ID in
memory and **Check result** still works after a connection error. A page reload
loses that memory fallback; wait for the old job to finish and refresh installed
status before starting another change.
Refresh the installed list before starting another
operation after an error. The headset panel and desktop app send the hash of
the version you saw; if the official store changes that version before the job
starts, Frame Control stops before downloading or changing the headset. Refresh
the store and review the new version before retrying. Job results live in server
memory for one hour after completion. If Frame Control restarts, or the request
never reached it, the panel cannot recover the result. It clears that ID and
keeps plugin changes disabled until **Refresh plugins** successfully reads the
installed list. An automatic status read does not clear this unknown outcome.
If browser session storage is denied, the unknown-result gate lasts for the
current open panel only; refresh installed status after reopening it.

An open plugin panel closes before its own Update or Remove starts, so its old
frontend cannot call the changing backend. Open panel is unavailable while a
store job is pending. A later installed-status refresh also closes an open panel
if Decky stopped, its store receipt changed, or the status read failed. Reopen
the plugin after a successful refresh to use its current frontend.
Chunked frontends load modules through URLs bound to the installed store
receipt. If a desktop store update replaces the plugin during panel startup,
old module requests fail and the panel must be reopened; Framey does not mix
chunks from two installed versions.
The headset also includes the panel's store SHA-256 receipt with each backend
call, Steam read, and event poll. It rejects a request if the installed receipt
changed before the next status refresh; reopen the panel to use the new version.
Panel-ready, error, and trusted-pointer reports also carry the current panel
session. A delayed report from a closed panel cannot change the new panel's
status or count as input to that panel.

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
`titleView` above it. A plugin with only `settings` opens that view directly;
Framey shows tabs only when both views exist. For one-tap headset controls, return
`frameyQuickActions: [{label: 'Refresh data', onClick: refreshData}]` from the
plugin initializer. Framey displays up to eight actions and reports a pending,
success, or failure state. It ignores extra taps while an action is pending,
and a failed action can be retried. Invalid action descriptors do not count
toward the eight-action limit. These descriptor fields are Framey additions; Decky
ignores them. Use a plugin backend method through `@decky/api` for work needing
persistent state, and keep a quick action safe to repeat.
See the [Decky API compatibility table](frame-plugin-author.md#framey-decky-api-compatibility)
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
