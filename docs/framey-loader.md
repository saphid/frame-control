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

Install, Update and Remove can restart the shared Decky service. After confirmation,
Framey closes any open plugin panel before submitting the change, including a
panel for a different plugin. It retires that panel's subscriptions and ignores
late replies from its old session. Refresh installed status and reopen the panel
to read saved settings again. Canceling confirmation keeps the panel open. A
failed or uncertain change leaves it closed; use **Check result** when offered
before reopening. Closing a panel does not cancel a backend save already sent
or prove that it persisted. These lifecycle checks use the shipped parent script
with synthetic replies; they add no live-headset or worn-VR proof.

Update and Remove recheck ownership under the transaction lock using a regular
store receipt file with a matching positive integer store ID. A symlinked,
unreadable or malformed receipt cannot authorize a change. Refused operations
leave the plugin and its data in place and do not stop the loader. Inventory
still lists readable plugin manifests without claiming store ownership when
their receipt or store ID is invalid.

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
folder with rollback on failure. If moving the installed folder to a backup
fails, the update or removal leaves the original folder in place. Rollback
deletes only a replacement that the transaction successfully moved into place.
It rejects non-ARM64 ELF and Windows binaries.
Before transfer, it streams every file through its ZIP checksum within the
existing archive size limits. Corruption after a file's header is rejected on
the host and by the local author checker. Remote extraction also rejects
checksum failures before changing the installed plugin or restarting Decky.
File/directory collisions are rejected before transfer and checked again on the
headset before extraction. For example, a file named `plugin/cache` cannot
coexist with `plugin/cache/` or `plugin/cache/data.json`, in either ZIP order.
Explicit directory entries remain optional; identical repeated file payloads
with only execute-bit differences are still accepted for official archives.
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
available. Plugins can enumerate non-reserved cache keys with `Object.keys`,
`Object.entries` or `for...in`, and export their string values with object spread
or `JSON.stringify(localStorage)`. API members are not enumerable; stored keys
that collide with API/prototype names still require `getItem` and `key(index)`.
If browser storage rejects a write, the parent keeps the latest
bounded snapshot in memory across plugin close/reopen and switches back to disk
on the next successful write. The plugin panel shows a notice while its snapshot
is only in memory. **Retry saving** attempts to save that latest snapshot without
changing a setting; a failed retry keeps the notice and values. A successful
retry clears only that plugin's notice. Reloading the Frame Control page loses that memory
fallback; an older disk snapshot may then return. Cleared browser storage also
loses saved caches. The host waits for the parent's cache reply before loading plugin code.
A failed browser-storage read or an invalid saved snapshot stops startup with an
error and leaves the saved bytes untouched; neither is treated as an empty cache.
Reopen the plugin after storage access recovers. Invalid saved data must be
recovered separately before the panel can open; Framey does not erase it automatically.
A valid in-memory snapshot from a failed write still works while disk reads are
blocked. Only a missing cache starts empty. A missing reply fails after five
seconds; explicit read errors and invalid replies fail immediately. Use
the plugin backend for settings that must survive cache loss.
The recovery notice, retry and readback after a full page reload are covered in
a local browser with synthetic snapshots and native browser storage. Live
headset persistence and worn-headset use remain unverified.

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
Framey also supplies the local `achievementClasses.AchievementListItemBase`
class map used by TabMaster's filter-selection rows. Replaying the complete
published row in local React/DOM verifies rendering and synthetic activation,
with private icon and MicroSDeck stand-ins. This adds no proof of TabMaster
library editing, live settings persistence or worn/controller use; its
compatibility rating is unchanged.

The host currently supplies sections, rows, buttons, toggles, text fields,
sliders, grouped dropdowns,
scroll containers, a modal, locale information, local panel routes and toasts,
and backend calls for the plugin that owns the panel. Text fields support
controlled values, uncontrolled defaults, and change, blur, focus, click and key
callbacks. These are ordinary input events; they do not open or verify SteamVR's
keyboard. The headset's scroll
buttons send only a direction to the isolated iframe. They target the last
scrollable region reached by a trusted pointer move and fall back to the iframe
document when that region disappears. A result message reports whether content
moved; this bridge has no backend or Steam privilege. Steam library/store page
patches, global Steam UI components, file pickers, and privileged root methods
have no VR target. A plugin that depends on them can render only part of its UI
or show an incompatibility message. A Decky plugin's Python backend still runs as
the headset user when Decky loads it, so review third-party code before opting
in. The panel iframe can make HTTPS requests subject to ordinary browser CORS.
Decky's proxy networking remains unavailable. Legacy `serverAPI.fetchNoCors`
resolves Decky's failure envelope, with `success: false` and a result explaining
that proxy fetch is not supported on Frame. Modern API v1/v2 `fetchNoCors`
rejects its promise. Neither fallback sends the request to a network or backend.
The file picker is also unavailable. Modern `openFilePicker` and legacy
`serverAPI.openFilePicker` / `openFilePickerV2` return rejected promises with
"Decky file picker is not supported on Frame", so plugins can use their normal
failure handlers. These methods do not select a path or browse headset files.

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
and progress bars. Its finite `DFL.IconsModule` supplies local `Search` and
`WiredNetworkWarning` SVGs so SteamGridDB's search field and image-error view
can render without dereferencing a missing namespace. These use local magnifier
and warning artwork, with the plugin's SVG props and styles; they do not expose
Steam's icon module. The exact published expressions render in a local browser,
but real artwork requests, live settings persistence and worn use remain unverified.
`SidebarNavigation` preserves each visible page's React
`icon` beside its title in the local navigation button, including icon props
and later updates. Separators and pages with `visible: false` do not become
buttons. This is local page selection; it does not recreate Steam's sidebar
layout or verify controller navigation.
Its explicit SteamClient subscription fallbacks return
disposable handles without emitting fabricated events. Running-game reads and
lifetime notifications use the scoped bridge described below; power, app launch
and hardware mutation methods are not supplied. Other live Steam stores require integration
work. IndexedDB is hidden because the browser exposes it but denies access in
an opaque iframe; localForage can then select Framey's bounded localStorage.
Direct IndexedDB users remain unsupported.

`SuspensefulImage` renders a native image. SteamClient `Storage.GetJSON` and
`SetObject` use the same bounded per-plugin cache, including panel reopen
persistence; they do not read Steam's account/global JSON store. `SetObject`
waits for the parent to save its snapshot in browser storage before resolving.
A rejected browser write rejects the call with an "only in memory" error;
the current value remains available in the panel and through **Retry saving**.
A missing reply rejects after five seconds, without claiming whether the write
committed. Reopen the panel to read the saved value before another edit.
This acknowledgement covers browser storage, not Decky's backend settings.
Missing keys
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

The desktop official store has Previous/Next buttons for all search results,
40 per page. Search matches names, authors and descriptions. A new search or
catalogue request returns to the first page; refreshing installed status keeps
the current page. Page information stays separate from catalogue and job errors.
Loading and failed catalogue requests clear old rows and disable navigation.
The page-script regression and private Chromium check use synthetic requests;
they do not prove live downloads, installs or headset behavior.

The in-headset **Open official store** view loads the full official catalogue.
Search matches names, authors, and descriptions. Filters show non-root plugins
or installed plugins, and Previous/Next buttons browse 20 results per page.
The catalogue's loading or error message stays visible when searching, changing
filters or refreshing installed plugins. A failed catalogue request does not
become an empty search result. Open the official store again to retry; a
successful catalogue response restores result counts and pagination. These
states are checked with synthetic requests through the headset page script;
they do not establish worn-headset visibility or controller behavior.
The root label is a compatibility warning; other APIs are checked only when a
plugin is opened. Both `root` and `_root`
store tags mark a plugin as needing root, and duplicate store IDs are omitted
because an ID alone could select a different archive than the visible row.
The store still needs the managed Decky user service running
before its Install or Update buttons are enabled. If a plugin prevents Decky
from starting, Remove remains available for Frame Control-owned plugins while
the managed service is stopped; it does not restart the service.
The desktop catalogue also keeps Remove for an installed managed copy when the
current store release needs root or is marked not supported on Frame. The
warning stays visible and Install/Update remains unavailable. Removal names the
installed copy and sends its reviewed receipt digest, rather than the blocked
release's name or archive digest. An upstream-only copy gets no managed Remove
action. These paths are covered with real local DOM controls and synthetic API
replies; they do not establish a live removal or worn-headset behavior.

Install, Update, and Remove show the current job stage in the headset panel.
The desktop store also reserves a request ID before sending a plugin change.
Its separate result message and **Check result** action recover that same job
without submitting the change again. Install, Update, Remove and loader changes
stay disabled through the job and final installed-status refresh, including
after a lost POST reply or exhausted polling retries. The saved request is
bound to the original headset; return to it to check the result. Session storage
retains the request through a page reload. If storage is denied, recovery is
limited to the current open page; a reload loses the memory fallback.
If the server no longer has the job, the desktop keeps changes disabled until
its **Refresh** button successfully reads a complete installed list. Automatic
reads, failed reads and acknowledgement changes do not clear that uncertainty.
An explicit HTTP rejection before the request was accepted releases the request;
a terminal job error also releases it after status refresh. These desktop paths
are tested with synthetic API replies and real DOM controls, not live installs.

Games Prefix Manager 1.0.1 installs the shared child IPC EOF repair alongside
its existing user-home and bounded-prefix safeguards, preserving its prior
managed backend body and other archive files. Existing copies need Update or
reinstall. Local AMD64 Decky 3.3.0 probes verify disposable multi-library
backup/delete, bulk-cleanup and symlink refusals, RPC after peer disconnect,
backup preservation across restart and two clean parent-only stops; restoring
the prior managed backend reproduces a forced kill after the same EOF. Real
Steam prefix changes, complete non-Steam names, managed Frame execution and
worn VR remain unverified. Fresh hosted architecture qualification is pending.

Pause Games 1.0.3 installs the shared child IPC EOF repair while preserving all
published process-control methods and other archive files. Existing copies need
Update or reinstall. Local AMD64 checks private settings and exclusions, RPC
after peer disconnect, restart persistence and two clean parent-only stops;
restoring the published backend reproduces a forced kill after the same EOF.
Actual game pausing, automatic pause, suspend integration and worn VR remain
unverified/unsupported. Fresh hosted architecture qualification is pending.

Network Sentinel 1.0.4 installs a child IPC EOF repair while preserving its
original monitoring and unload code. Existing managed copies need Update or
reinstall to receive it. The isolated runtime gate requires a settings RPC after
peer disconnect, the original unload save, restart persistence and two clean
parent-only stops; a negative control restores the previous managed backend.
External network quality, the real headset and worn VR remain unverified.

Mixer 0.1.0 installs the shared child IPC EOF repair while preserving its
original backend body and all other archive files. Existing copies need Update
or reinstall. Local AMD64 Decky 3.3.0 probes run under UID 1100 without a
`PULSE_SERVER` override against private silent PipeWire/WirePlumber streams and
verify per-stream volume readback, invalid regex rejection, filter and boost
limit persistence across restart, `reset_volumes`, post-EOF RPC and two strict
parent-only stops; restoring the published backend reproduces a forced
`SIGKILL` after peer EOF. Internal audio nodes, audible output, Bluetooth
playback, adapted ARM64/Frame execution and worn VR remain unverified; see
[the native evidence](evidence/framey-mixer-child-ipc-2026-11-21.md).

DeckyFileServer 1.2.0 also installs the child IPC EOF repair. Its managed
backend, HTTPS helper and original unload hook are preserved; existing copies
need Update or reinstall. The native runtime gate closes a private IPC peer,
requires a subsequent settings RPC, checks two clean parent-only stops and
restart persistence, and restores the previous backend as a negative control.
This does not establish the historical ARM64 migration timeout's cause or add
real Frame or worn/controller proof.

PlayTime 3.2.5 installs the shared child IPC EOF repair while preserving its
original backend body and all other archive files. Existing copies need Update
or reinstall. Local AMD64 Decky 3.3.0 probes verify private per-user SQLite
sessions, paused-session refusal, RPC after peer disconnect, restart persistence
and two clean parent-only stops running the original unload hook; restoring the
published backend reproduces a forced kill after the same EOF. Automatic
recording, live Frame execution and worn VR remain unverified; fresh hosted
architecture qualification is pending.

Volume Boost 0.0.7 preserves the actual user's `XDG_RUNTIME_DIR` (falling back
to `/run/user/<uid>` instead of hard-coded `/run/user/1000`) and installs the
shared child IPC EOF repair while preserving every other archive file. Existing
copies need Update or reinstall. Local AMD64 Decky 3.3.0 probes run under UID
1100 without a `PULSE_SERVER` override against private silent PipeWire/Pulse
null sinks and verify linked boost (`125%`/`150%`), separate left/right writes,
re-link, an unrelated null sink, post-EOF RPC readback, restart and two strict
parent-only stops. Two negative controls reproduce the original wrong-user Pulse
failure and the pre-EOF forced `SIGKILL` shutdown. Audible output, Bluetooth
sinks, adapted ARM64/Frame execution and worn VR remain unverified; see
[the native evidence](evidence/framey-volume-boost-user-runtime-2026-11-21.md).

Tailscale Control 0.1.3 preserves the actual user's `XDG_RUNTIME_DIR` (falling
back to `/run/user/<uid>` instead of hard-coded `/run/user/1000`), adds the
active user's `~/.local/bin` and `~/.nix-profile/bin` alongside `/opt/tailscale`
to `PATH`, fixes `up()` and `down()` to return `returncode == 0` instead of
`not CompletedProcess` / unconditional `True`, and installs the shared child IPC
EOF repair while preserving every other archive file. Existing copies need
Update or reinstall. Local AMD64 Decky 3.3.0 probes run under UID 1100 with
`--network=none` against a private disposable `~/.local/bin/tailscale` stub
without `~/.local/bin` in the initial `PATH` and verify state/exit-node/device
readbacks, truthful `up()`/`down()` exit booleans, preserved `XDG_RUNTIME_DIR`,
post-EOF RPC, restart and two strict parent-only stops. Two negative controls
reproduce the original `~/.local/bin` CLI discovery failure and pre-EOF forced
`SIGKILL` shutdown. Real `tailscaled`, live tailnet/exit-node changes, bundled
localhost QR asset, adapted ARM64/Frame execution and worn VR remain unverified;
see [the native evidence](evidence/framey-tailscale-control-runtime-2026-11-21.md).

Junk-Store 1.1.13 removes `Helper.ws_loop.stop()` and loop-wide
`asyncio.all_tasks()` cancellation from unload (leaving Decky's shared event
loop and IPC/unload tasks intact so `_unload` finishes without crashing in
`RecursionError`) and installs the shared child IPC EOF repair while preserving
all other archive files and script execute permissions. Existing copies need
Update or reinstall. Local AMD64 Decky 3.3.0 probes run under UID 1100 with
`--network=none` and verify static menu actions, localhost WebSocket startup and
teardown, post-EOF RPC, restart and two strict parent-only stops completing
Junk-Store's unload hook. Two negative controls reproduce the original
`RecursionError` unload crash on `SIGTERM` and the pre-EOF forced `SIGKILL`
shutdown. Legendary, login, game operations, RSS, WebSocket commands, adapted
ARM64/Frame unload and worn VR remain unverified; see
[the native evidence](evidence/framey-junk-store-unload-2026-11-21.md).

The store verifies each downloaded archive and the headset applies it with a
rollback if Decky cannot start. The panel saves a random request ID before
submitting a change. The server uses that ID as the job ID and returns the
same job for a repeated, identical request while its result is retained;
reusing the ID for a different change is rejected. Invalid plugin IDs and
malformed reviewed store hashes receive HTTP 400 before a job is reserved or
a worker starts. A corrected request can use the ID from that rejected
submission. **Check result** can resume
polling even if the POST response is lost. A rejected polling request also keeps
an accepted job's ID; it cannot establish that the install or update stopped.
After a connection error, Install, Update, and Remove
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
the store and review the new version before retrying.
The desktop and headset also include the installed receipt shown by the Update
or Remove row. If another client changes that installed copy before the job
starts, the operation stops before downloading or changing plugin files. Refresh
installed plugins and review the current copy before trying again. The existing
transaction lock checks the receipt again before applying the operation.
An install also rechecks the store ID under that lock. If another client has
installed that ID since the first status read, the later install stops before
changing files or stopping Decky, even if the store changed its name and folder.
Refresh installed plugins and use Update or Remove; a changed folder still
requires removing the old version before installing the new one.
Job results live in server memory for one hour after completion. If Frame Control restarts, or the request
never reached it, the panel cannot recover the result. It clears that ID and
keeps plugin changes disabled until **Refresh plugins** successfully reads the
installed list. An automatic status read does not clear this unknown outcome.
If browser session storage is denied, the unknown-result gate lasts for the
current open panel only; refresh installed status after reopening it.

If the server cannot create or start the background worker, **Check result**
reports a completed startup error. Checking does not retry the plugin change.
Refresh installed status before starting a fresh action after the error.

An open plugin panel closes before its own Update or Remove starts, so its old
frontend cannot call the changing backend. Open panel is unavailable while a
store job is pending. A later installed-status refresh also closes an open panel
if Decky stopped, its store receipt changed, or the status read failed. Reopen
the plugin after a successful refresh to use its current frontend.
While installed status is being refreshed, the headset page clears old
installed rows and disables store changes. Callbacks retained from those rows
cannot prompt or submit until a complete status read succeeds. Failed or
incomplete reads (including a missing managed flag) keep changes blocked; an
unmanaged loader state disables Remove and store actions (while Open panel
requires Decky to be running), and a successful stopped managed status keeps
recovery removal available while requiring Decky to run for installs and updates.
Active store changes and **Check result** polls keep installed controls, store
actions and **Check result** disabled until the final installed-status refresh
finishes. These headset-panel guards are tested with synthetic status and job
replies through the shipped headset page script; they do not establish live
headset or worn-VR behavior.
Chunked frontends load modules through URLs bound to the installed store
receipt. If a desktop store update replaces the plugin during panel startup,
old module requests fail and the panel must be reopened; Framey does not mix
chunks from two installed versions.
The headset also includes the panel's store SHA-256 receipt with each backend
call, Steam read, and event poll. It rejects a request if the installed receipt
changed before the next status refresh; reopen the panel to use the new version.

Catalog and installed plugin names stay complete when validating archives,
checking name collisions, and routing backend calls or event subscriptions.
Long names that share a prefix remain distinct; display-length truncation must
not change a plugin's backend identity. The existing catalog-response and
installed-manifest size limits still apply. These paths are tested locally
with synthetic names and disposable manifests, without a live headset.

An installed plugin with a non-object JSON manifest is skipped during inventory
instead of hiding every plugin. A readable manifest with a non-object ownership
receipt stays visible as unowned, without store actions or a managed Framey
panel. The scan leaves those files untouched; after repair, a fresh inventory
reads them again. These cases are tested with disposable local plugin folders.
Panel and JavaScript module admission also require a positive integer `storeId`
in the ownership receipt. JSON booleans and floating-point IDs cannot claim an
integer plugin ID or mask a valid installed plugin during the panel scan.
Malformed receipts are left untouched. Local fixtures cover rejection and
recovery after repairing the ID; live-headset behavior remains unverified.

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
Its JSON `passed` value reports machine checks only; the separate worn-visual
and physical-controller verification fields remain false in this script.
Record human evidence separately.


## Unattended VR checks

The [unattended check](framey-vr-check.md) can wake, inspect and capture the
real compositor, send OpenVR mouse input, and exercise a temporary sample
against live Decky with restoration and shared-lock protection. Its
[device evidence](evidence/framey-vr-2026-10-25/README.md) distinguishes these
checks from physical controller and wearer validation. A trusted pointer event
and active-headset telemetry are both reproducible without wearing the Frame;
they must not be labelled as physical controller proof.
