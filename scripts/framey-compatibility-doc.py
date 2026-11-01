#!/usr/bin/env python3
"""Render the documentation from the same digest-scoped data used by the store."""
import argparse
from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def cell(value):
    if isinstance(value, list):
        value = ', '.join(str(v) for v in value) or 'none detected'
    return str(value).replace('|', '&#124;').replace('\n', ' ').replace('<', '&lt;')


def render(data):
    counts = Counter(p['status'] for p in data['plugins'])
    lines = ['# Official Decky store compatibility with Framey', '',
        f"Snapshot: {data['checkedAtUtc']}; {len(data['plugins'])} current visible official plugins from {data['source']}.", '',
        'This table and both store views use [`ui/framey-compatibility.json`](../ui/framey-compatibility.json). '
        'Results apply only to the exact store ID, version and SHA-256. A changed digest/version is **unverified**. '
        'Regenerate this document with `python3 scripts/framey-compatibility-doc.py`; use `--check` in review.', '',
        f"**Works: {counts['works']} · Partial: {counts['partial']} · Broken: {counts['broken']} · N/A: {counts['na']}.**", '',
        '- **Works** requires verified useful plugin behavior with its real backend. Read the reason for the verified scope and remaining limits; it does not imply worn-VR verification.',
        '- **Partial** means only a subset or a local fixture scope was verified, often just frontend/settings initialization. The remaining backend/device functionality is unverified; read the reason for the exact scope.',
        '- **Broken** means a concrete archive, frontend or Steam dependency blocks the audited version. An artificial backend/network denial alone is not evidence that the real backend is broken.',
        '- **N/A** means the plugin targets hardware or a display/UI surface that Framey does not provide. The store disables installation for these versions.', '',
        '## Verification limits', '',
        f"All exact archives were hash-checked and statically inspected. The local Chromium host used Framey commit `{data['hostCommit']}`, React 18.3.1 and an opaque `allow-scripts` iframe. "
        'Each frontend was attempted for 1.2 seconds, including React effects. All plugin backend calls, fetches and websockets were denied in this original catalog sweep; separately linked focused replays may use private fixtures. '
        'Some plugins attempt mutating actions on mount; none reached a backend. Initialization (`ready`) does not guarantee React rendered, and delayed errors/actions may occur after the observation window. '
        'The JSON preserves initializer errors, capped console observations and attempted method names.', '',
        'The optional full-catalog fake-Frame audit exercises the real HTTP/SSH installer, receipt, frontend bytes and removal, '
        'or expected rejection. It uses a private disposable Compose project with all plugin backend execution stubbed. '
        'It checks archive transport and safeguards, not Python/native execution. Run it with:', '',
        '```sh',
        'python3 scripts/framey-audit-store.py --cache /tmp/framey-archives --output /tmp/framey-observations.json',
        'python3 scripts/framey-audit-fake.py --cache /tmp/framey-archives --output /tmp/framey-fake/results.json',
        'python3 scripts/framey-audit-browser.py --cache /tmp/framey-archives',
        '```', '',
        'Open the browser audit URL in local Chromium, run `runAudit()` and inspect/download `results`. All backend/network actions remain denied.', '',
        'A [Game Sync selection follow-up](evidence/framey-game-sync-selection-2026-10-30.md) bounds the exact managed 1.0.4 read-only selection check to its configured root, including linked files and directories. '
        'Published Decky 3.3.0 x86_64 verifies private selection RPCs, outside-path and cycle refusals, and restart persistence. Existing copies need Update/reinstall. '
        'This does not sandbox rclone execution: its amd64 updater, default --copy-links arguments, cloud sync, process signals, revised ARM64 check, real Frame and worn/controller use remain unverified. Game Sync stays partial.', '',
        'A [DeckyParty lifecycle follow-up](evidence/framey-deckyparty-lifecycle-2026-10-30.md) runs the exact official 1.0.0 helper as the actual service user without sudo, isolates its temporary cache and reaps its owned process session. '
        'Published Decky 3.3.0 AMD64/ARM64 verify authenticated private listing/download/upload/delete, refusal of anonymous/wrong-password reads, disable/restart and actual plugin reload cleanup. '
        'A [child IPC EOF follow-up](evidence/framey-deckyparty-ipc-eof-2026-10-31.md) addresses an intermittent forced-kill reload reproduced by new hosted AMD64 and unchanged-main local runs. The exact managed archive now receives the existing child-local EOF adapter. Fresh local AMD64 verifies three reloads and a parent-only stop; fresh ARM64 and full hosted qualification remain pending. '
        'The fixture uses an owned disposable disk volume; Copyparty\'s refusal to upload into tmpfs remains intact. LAN/HTTPS, external media, real Frame backend, panel controls and worn/controller use remain unverified. Existing copies need Update/reinstall. '
        'A [2026-10-30 full-catalog transport regression](evidence/framey-catalog-transport-2026-10-30.md) rechecked all 116 published versions/digests: 69 installed and were removed, and 47 were refused as expected in an owned fake Frame. No official backend executed in that audit and no functionality rating follows from transport success. '
        'A [Games Prefix Manager follow-up](evidence/framey-prefix-manager-2026-10-29.md) enables only the exact managed 1.0.1 archive as a user-service plugin. '
        'It reads the actual user home and current Steam library format, bounds prefix deletion, preserves separate backups and reports refused actions in the panel. App IDs appearing in multiple rows are refused without backup or deletion. '
        'Published Decky 3.3.0 x86_64 and local Chromium verify only disposable prefix backups/deletions; a locked real ARM64 Frame service verifies discovery and read-only listing. '
        'Automatic orphan cleanup is disabled; unmatched prefixes are labeled Unidentified because non-Steam shortcut coverage is incomplete. Actual Decky RPC fixtures preserve a second user’s prefix with malformed or unreadable shortcuts. Symlink prefixes and backups containing symlinks or special files are refused. Real prefix changes, complete non-Steam names and worn VR remain unverified, so the plugin is partial. '
        'An independent cleanup audit passed and battery stayed 100 → 100. A fresh store read on 2026-10-29 confirmed all 116 catalog version/digest records unchanged.', '',
        'An [upstream Games Prefix Manager v1.0.2 preflight](evidence/framey-prefix-manager-102-2026-10-30.md) pins the separate GitHub release asset while the live Decky store still serves 1.0.1. Its exact managed copy refuses the new game-data deletion option before changing files. Published Decky 3.3.0 x86_64 checked private prefix RPCs, and local Chromium rendered the managed panel with the option hidden. The catalog row and published classification remain for store 1.0.1; v1.0.2 has no live Frame or worn-VR verification.', '',
        'A [Shotty copy-boundary follow-up](evidence/framey-shotty-bounded-2026-10-30.md) confines output paths, refuses symlinks and ambiguous account matches, preserves conflicting images and makes independent copies across filesystems. '
        'Published Decky 3.3.0 x86_64 verifies private selected-copy and historical-aggregation RPCs; the local runtime proof is x86_64 only, and real Frame screenshots, continuous rescue and worn/controller use remain unverified. Existing installs need Update/reinstall.', '',
        'A [Shotty unload follow-up](evidence/framey-shotty-unload-2026-10-31.md) applies the existing child-local IPC EOF repair only to the exact managed 0.1.0 archive. Local published Decky 3.3.0 AMD64 verifies two clean parent-only stops, restart and a prior-source forced-kill negative. Fresh ARM64 unload and full hosted qualification remain pending; Shotty stays partial. Update/reinstall is required.', '',
        'A [Download All queue follow-up](evidence/framey-download-all-2026-10-30.md) enables only the exact managed 1.1.0 archive. '
        'An opaque local Chromium panel with synthetic Steam callbacks verifies Scheduled/All/size filters, smallest-first append, existing-queue resume and visible partial failure. '
        'Published Decky 3.3.0 AMD64 and ARM64 verify discovery and logging RPC only. Actual Steam queue changes, ARM64 Frame runtime, headset rendering and physical controller use remain unverified; the plugin is partial and older copies require update/reinstall.', '',
        'A [Desktop Apps and Download All native follow-up](evidence/framey-desktop-download-native-followup-2026-10-30.md) independently audits both exact plugin archives in published Decky 3.3.0 AMD64 and ARM64 CI. Desktop Apps verifies private desktop-entry filtering, settings persistence and temporary-shortcut bookkeeping after a loader restart. Download All verifies only discovery and backend logging. Actual Flatpak discovery, Steam shortcut or queue changes, app launches, real Frame runtime, browser/backend integration and worn/controller use remain unverified; both plugins stay partial.', '',
        'A [Free Loader duplicate-entry follow-up](evidence/framey-free-loader-duplicates-2026-10-26.md) accepts only byte-identical duplicate ZIP members whose modes differ at most in execute bits. The exact archive passed private local and focused fake-Frame install/remove; its frontend rendered in opaque Chromium. The earlier full 116-plugin fake-Frame audit blocked this archive before the fix. A later [native Decky 3.3.0 check](evidence/framey-free-loader-native-2026-10-28.md) verified plugin discovery, default settings, empty local deals and private setting persistence after restart in network-isolated amd64 and ARM64 containers. Live feed updates, notifications, Steam store integration, real Frame ARM64 service and worn VR remain unverified.', '',
        'A [2026-10-28 static action-limit review](evidence/framey-static-action-limits-2026-10-28.md) hash-checked the exact AutoSuspend and CheatDeck archives. AutoSuspend contains Steam suspend/shutdown paths, and CheatDeck\'s advertised trainer flow needs a Steam game context menu and launch-option writes. Neither plugin was executed; both retain their broken labels.', '',
        'A [Decky-Framegen archive-limit check](evidence/framey-framegen-archive-limit-2026-10-29.md) confirmed that the official 0.11.15 ZIP matches its published SHA-256 but exceeds Framey\'s 50 MiB managed download cap. The installer still blocks it, and its OptiScaler/Proton game modifications remain untested.', '',
        'A [Game Theme Music native backend check](evidence/framey-game-theme-music-native-2026-10-29.md) discovered the unmodified exact 1.7.1-1 archive in published Decky 3.3.0 x86_64 and verified a private setting across a loader restart in a networkless disposable container. A separate [local settings replay](evidence/framey-game-theme-music-settings-2026-10-29.md) verified mute, volume and yt-dlp controls through Framey\'s iframe transport with in-memory replies. The panel was not connected to the native backend. Search, downloads, playback, Steam game-page injection, real Frame and worn VR remain unverified; the plugin stays partial.', '',
        'A [Deck Settings upload safety follow-up](evidence/framey-deck-settings-tls-2026-10-29.md) restores certificate and hostname checks in the exact managed 1.2.6 backend. Published Decky 3.3.0 x86_64 passed read-only RPCs, and the installed helper rejected private self-signed loopback HTTPS before sending a fixture bearer header. Public uploads, report lookups, settings changes, real Frame and worn VR remain unverified; the plugin stays partial.', '',
        'A [Steam Status TLS follow-up](evidence/framey-steam-status-tls-2026-10-29.md) retains certificate and hostname checks for the exact managed 1.2.3 public CM-list and speed-test downloads. Local tests exercise both contexts with network denied. Published Decky 3.3.0 x86_64 discovers the managed backend and reads private defaults; a [private settings follow-up](evidence/framey-steam-status-persistence-2026-10-30.md) verifies setting write/read and restart persistence in isolated x86_64 and ARM64. Live public diagnostics, real Frame use of the adapted backend and worn VR remain unverified; the plugin stays partial.', '',
        'A [static EmuDecky startup audit](evidence/framey-emudecky-static-2026-10-29.md) hash-checked the exact 1.0.2-1 archive. Besides its x86_64 helper and root flag, the backend would run git reset --hard and git pull on load in the user\'s EmuDeck checkout. The plugin was not executed and remains blocked.', '',
        'A [Network Sentinel user-service check](evidence/framey-network-sentinel-2026-10-28.md) adapts only the exact 1.0.4 digest. In isolated actual Decky 3.3.0 amd64 and ARM64, the pinned plugin-local psutil wheel, private settings RPC and one monitoring-loop sample pass. External ping/DNS, a real Frame backend, panel controls and worn VR remain unverified; this is partial compatibility.', '',
        'A [Battery Tracker user-service check](evidence/framey-battery-tracker-2026-10-28.md) adapts only the exact 0.2.0 digest. A locked read-only Frame probe confirmed a Battery-type supply with the required fields; actual Decky 3.3.0 amd64 and ARM64 recorded private Frame-shaped samples and returned history/per-app power. A [local panel replay](evidence/framey-battery-panel-fixture-2026-10-29.md) rendered synthetic history and lookback controls in Chromium. The managed plugin has not run on the real Frame; real Frame panel controls and worn VR remain unverified. This is partial compatibility.', '',
        'A [Decky Notifications private backend check](evidence/framey-decky-notifications-2026-10-29.md) removes a shared `/tmp` log and an environment dump only for the exact 1.0.1 digest. Actual Decky 3.3.0 amd64 and ARM64 in network- and device-isolated containers passed private certificate creation, empty device list, synthetic notification read/clear and restart. A separate [opaque Chromium panel check](evidence/framey-decky-notifications-panel-2026-10-29.md) displays a synthetic trusted device and notification using in-memory replies. Phone pairing, LAN delivery, real Frame backend, live panel delivery and worn VR remain unverified; this is partial compatibility.', '',
        'A [Discord Status IPC lifecycle follow-up](evidence/framey-discord-ipc-lifecycle-2026-11-01.md) adapts only the exact managed 1.5.0 archive. Published Decky 3.3.0 AMD64, with a disposable private wire peer, verified original handshake/activity payloads, replacement, clear, failed-handshake retry and clean unload/restart. Real Discord accounts/activity, Steam callbacks, shortcut detection, artwork, browser controls, real Frame and worn/controller use remain unverified; compatibility stays partial. Original blocking receive/framing and Flatpak path assumptions are not repaired by this change.', '',
        'An [Animation Changer override follow-up](evidence/framey-animation-overrides-2026-11-01.md) preserves existing movies for empty default selections and validates sources before replacement, only for the exact managed 1.3.2 archive. Native published Decky 3.3.0 AMD64 verifies private apply/repeat/switch/reset RPCs for all three movie names and restores original bytes and inodes. Existing copies need Update/reinstall. Abrupt interruption recovery, native ARM64, downloads, legacy user-data migration, actual Steam playback, real Frame and worn/controller use remain unverified; compatibility stays partial.', '',
        'The current published digests are pinned in the JSON; if the store changed, retain/download those exact archives for reproduction. '
        'Audit downloads permit larger ZIPs for inspection; production installer limits remain 50 MiB ZIP / 150 MiB unpacked / 30 MiB per member.', '',
        'After the VR job released the shared lock, this audit acquired it and used a private temporary Decky 3.3.0 ARM64 user service. '
        'Read-only ProtonDB `get_setting` and Steam Status `get_settings` calls succeeded through the live Steam CEF websocket. '
        'The service and private base were removed and the lock released; normal managed services stayed inactive, battery was 100 → 99, '
        'and no power setting was changed. [Redacted results](evidence/framey-official-backend-2026-10-25.json) '
        'record exactly what ran. A [2026-10-26 follow-up](evidence/framey-events-backend-2026-10-26.json) '
        'verified default Notebook drawing/save/reopen across a real backend restart and Simple Timer start/cancel, '
        'countdown/completion events, a visible toast and persisted recents/subtle mode. '
        'Only private test settings were written. That initial pass left Simple Timer partial because its own expired-timer startup '
        'raises a missing `timer_task` error; sound/suspend are unsupported. '
        'A [local audio follow-up](evidence/framey-audio-backends-2026-10-26.md) exercised Volume Mixer, Volume Boost and Mixer '
        'through real Decky 3.3.0 amd64 backends on private silent virtual audio targets. Sliders, numeric volume entry, '
        'independent server readbacks and Mixer filter persistence across a runtime restart passed. '
        'An [ARM64 audio follow-up](evidence/framey-audio-arm64-2026-10-26.md) verified the unmodified official backends in actual Decky 3.3.0 on the Frame user audio session. Volume Mixer and Mixer now qualify as works for per-app volume: Chromium controls changed only a named silent stream, with independent Pulse readbacks. That run left Volume Boost partial because sink writes were denied. A [Volume Boost follow-up](evidence/framey-volume-boost-arm64-2026-10-26.md) now verifies linked/separate channel controls, re-link and reopen through the actual ARM64 backend. Independent Pulse reads confirmed 125%/150% gain writes while the default sink stayed muted; exact original volume/mute was restored. Volume Boost qualifies as works for sink controls. Audible output, Bluetooth playback and worn VR remain unverified. '
        'A [running-context follow-up](evidence/framey-running-context-2026-10-26.md) supplies detached running-app/main-app reads and relays actual Steam lifetime callbacks while a panel is open. Real Frame checks verified an empty list, registration/cleanup and the exact Discord Status ARM64 backend reporting no IPC connection. Nonempty games and transitions were synthetic fixtures; real game events, Discord activity and worn VR remain unverified. Discord Status moves to partial; no new works claim is made. '
        'A [library context follow-up](evidence/framey-library-context-2026-10-26.md) read 1,106 app overviews, 895 game IDs '
        'and the current public Steam ID from real Frame CEF under the shared lock. Local Chromium replayed this detached snapshot '
        'to render Deck Settings game selection, Steamback\'s empty save panel and PlayTime statistics/settings. '
        'Steamback and PlayTime used actual Decky 3.3.0 amd64 backends in an isolated container; their ARM64 backends and automatic game hooks remain unverified. '
        'Shotty initially failed on missing `click`. Its [managed Python fix](evidence/framey-shotty-python-2026-10-26.md) and [native copy RPC check](evidence/framey-shotty-rpc-2026-10-28.md) moved it to partial. '
        'A [chunked frontend follow-up](evidence/framey-deck-shelves-browser-2026-10-26.md) loaded Deck Shelves 2.0.0 '
        'through a managed JavaScript module route and rendered its settings in an opaque local Chromium panel. '
        'Its backend was denied; Steam Home shelves and worn VR remain unverified. '
        'A [local module lookup follow-up](evidence/framey-module-lookup-2026-10-26.md) supplies a finite registry of Framey-local controls and CSS. TabMaster QAM/docs now render; Steam library-tab editing remains unavailable. That pass exposed Junk-Store executable-script extraction failures; the follow-up below repairs them. SteamGridDB still requires Steam context-menu internals and DeckSP still fails its published MobX fallback. That pass tested TabMaster/Junk-Store in actual isolated amd64 Decky, without ARM64 or worn-VR coverage. A [script entrypoint follow-up](evidence/framey-script-entrypoints-2026-10-26.md) grants owner execute to shebang scripts and ZIP-declared executables without copying archive privilege/write bits. Junk-Store now passes static menu/backend calls in actual Decky 3.3.0 ARM64 and local Chromium Games/Epic navigation, back and reopen. It moves to partial: About still crashes on missing installed-app metadata, Legendary is absent, and login/game operations remain unverified. Existing installations require update/reinstall to repair permissions. A [read-only installed-metadata follow-up](evidence/framey-installed-context-2026-10-26.md) now repairs the About crash. The library snapshot copies only Steam-supplied installed booleans into detached metadata, preserving unknown values as undefined. Junk-Store About/Dependencies, Back and reopen render in local Chromium with actual Frame library data and the official ARM64 backend. It remains partial: dependency/login/game operations, RSS, the optional websocket and worn VR are unverified. Beyond the documented checks, official backends remain unexecuted. '
        'The separate VR job proves Frame Control/sample compositor rendering, not any official plugin. '
        'No worn-VR official-plugin result is claimed. '
        'A [local UI follow-up](evidence/framey-ui-fallbacks-2026-10-26.json) rendered Pause Games and Tailscale Control settings '
        'with all backend/network actions denied; it does not verify process pausing or Tailscale changes. '
        'A [read-only Steam bridge follow-up](evidence/framey-steam-reads-2026-10-26.json) verified actual Frame country, '
        'install folders and system information, plus IsThereAnyDeal\'s country dropdown in local Chromium. '
        'The installed-plugin status was fixture-shaped in that relay; plugin backends stayed denied and the deployed headset HTTP endpoint remains unverified. '
        'A [Web Browser frontend follow-up](evidence/framey-web-browser-2026-10-26.md) verified its exact archive now initializes with an inert null Steam React-root lookup. Its GamepadUI CDP/browser backend path remains unavailable, so it stays broken. '
        'A [dialog and activation follow-up](evidence/framey-dialog-controls-2026-10-26.md) fixes DFL Focusable pointer/keyboard activation and confirmation descriptions, cancel/disabled actions, scoped close callbacks and nested dialogs. '
        'AlarMe silent timer ticks/pause/cancel, private preset save/cancel-confirm/delete and stopwatch start/lap/pause/reset/reopen pass in local Chromium with its official Decky 3.3.0 ARM64 backend. '
        'AlarMe stays partial: audio, alarms/reminders, sleep inhibition, Steam overlays and worn VR are unverified; notifications require the panel to remain open. '
        'Earlier focused checks cover [ProtonDB](evidence/framey-browser-2026-10-25.md), '
        '[Steam Status/cache](evidence/framey-cache-browser-2026-10-25.md), '
        '[Storage Cleaner](evidence/framey-api-v1-browser-2026-10-25.md), and '
        '[legacy MusicControl](evidence/framey-legacy-2026-10-25.md). '
        'A [shared Music Control runtime follow-up](evidence/framey-mpris-runtime-2026-10-26.md) corrects the earlier bound-method fixture error: actual Decky uses the legacy class calling convention, so explicit-self calls must stay. '
        'Exact managed installs also restore the system library path for D-Bus subprocesses, repairing a real Frame OS libtinfo/glibc failure in MusicControl 1.1.6. '
        'Both official entries pass transport/seek/volume, Info and reopen in local Chromium with actual Decky 3.3.0 amd64 and a private silent MPRIS service. '
        'Actual ARM64 Decky on the Frame passes read-only empty-player discovery for both. Existing copies need remove/reinstall or an explicit managed update. '
        'Actual media playback on ARM64, artwork and worn VR remain unverified; both stay partial. '
        'A [DeckySpy follow-up](evidence/framey-deckyspy-2026-10-26.md) repairs its omitted psutil dependency with pinned BSD stable-ABI amd64/ARM64 wheels and a plugin-local Frame battery-name fallback. '
        'Its actual Decky 3.3.0 ARM64 backend passed read-only metrics under the shared lock, with memory independently matched to /proc/meminfo. '
        'Local opaque Chromium used that live ARM64 backend to render CPU, memory, battery, processes and interfaces, display a silent warning toast and save/reopen a private refresh setting. '
        'DeckySpy qualifies as works for system monitoring while its panel is open. Automatic alerts, resume/game-time warnings, sound and worn VR remain unverified. '
        'Cleanup and an independent removal audit passed; battery stayed 100 → 100 and original service states were preserved. Existing copies need update/reinstall. '
        'A [Simple Timer lifecycle follow-up](evidence/framey-simple-timer-2026-10-26.md) repairs fresh/expired startup cancellation, '
        'canceled deadlines that resumed and replaced tasks that still notified. Exact managed installs retain the API1 instance convention. '
        'Published Decky 3.3.0 discovery/RPC/events verify cancel, replacement, completion and active/canceled/expired restarts in isolation; '
        'the real ARM64 Frame repeats those lifecycle checks under the shared lock. Local Chromium with that live backend verifies '
        'Begin/Cancel, countdown and a silent completion toast. Simple Timer qualifies as works for silent in-panel session timers. '
        'Update/reinstall is required; old receipts stay partial. Sound/suspend are unsupported, closed-panel alerts and worn VR unverified. '
        'The private service, files, test listeners and processes were removed; independent cleanup audit passed and battery stayed 99 → 99. '
        'A [shared Toggle follow-up](evidence/framey-toggle-2026-10-27.md) separates standalone Toggle.value from ToggleField.checked. '
        'Nine official archives consume this API; their remaining blockers and status labels are preserved. '
        'Local opaque Chromium controls and the exact Pause Games frontend callback pass. Actual published Decky 3.3.0 discovery and '
        'private settings/exclusion-list persistence pass on amd64 and the ARM64 Frame through the normal CEF bridge. '
        'Process control and worn VR remain unverified; independent cleanup audit passed.', '',
        '## Every current plugin', '',
        'The API column shows manifest / actual bundled frontend API. Many manifests say v1 while their bundle connects API2. '
        'Missing manifest API is labelled legacy; an unrecognized bundle is unknown. Globals and hardware are static signals, not exhaustive dependencies.', '',
        '| Plugin / version | Manifest / bundle API | Status | Reason | Verified by |',
        '| --- | --- | --- | --- | --- |']
    for p in data['plugins']:
        lines.append('| '+ ' | '.join(map(cell, [f"{p['id']}: {p['name']} {p['version']}",
            f"{p['api']} / {p['frontendApi']}", 'N/A' if p['status']=='na' else p['status'], p['reason'], p['verification']]))+' |')
    lines += ['', '## API, UI and backend inventory', '',
        'DFL includes exports imported through decky-frontend-lib / @decky/ui. Steam stores and router/toaster/QAM signals are listed separately. '
        'No signal means the static scan did not detect one, not that no dependency exists. Native binaries are classified by ELF machine or Windows MZ header; '
        'Python files and source links are preserved in the JSON.', '',
        '| Plugin | SteamClient methods | DFL / @decky/ui exports | Other Steam globals / UI surfaces | Backend | Hardware / OS signals |',
        '| --- | --- | --- | --- | --- | --- |']
    for p in data['plugins']:
        native = sorted({n['arch'] for n in p['native']})
        lines.append('| '+' | '.join(map(cell, [p['name'],p['steamClient'],p['dfl'],p['globals']+p.get('uiSurfaces',[]),
            p['backend']+('; '+', '.join(native) if native else ''),p['hardware']]))+' |')
    lines += ['', '## Native payload portability', '',
        'All published Linux native payloads in this snapshot are x86_64; no published aarch64 payload was found. '
        'The three Windows DLLs belong to Decky-Framegen. Only the exact managed DeckyFileServer, Decky Localsend, Emuchievements and Wine Cellar adaptations below can replace their published x86 helpers; other x86 archives remain blocked. '
        'The native compatibility constraints below remain specific to each plugin.', '',
        'A [DeckyFileServer ARM64 follow-up](evidence/framey-fileserver-arm64-2026-10-27.md) ships an offline, digest-checked GPL helper build, corresponding vendored source and a build recipe. '
        'Only its exact managed archive can replace the x86 helper and remove its unnecessary root flag. Actual Decky 3.3.0 discovery/RPC and real Frame HTTPS private-fixture listing/download pass; uploads stay disabled. '
        'Hostname-DNS failures and empty optional arguments are repaired. Decky 3.3.0 still exposes `decky.HOME`; that call is unchanged. '
        'The plugin remains partial. A [frontend URL follow-up](evidence/framey-fileserver-url-2026-10-28.md) changes only the exact managed bundle to display the backend-returned IP with HTTPS, matching the helper. A [directory-entry follow-up](evidence/framey-fileserver-path-entry-2026-10-29.md) provides an explicit path field in that managed panel while retaining saved history; it does not grant a generic file picker. Existing managed copies need update or reinstall. Live directory entry, uploads, generated thumbnails and worn VR remain unverified.', '',
        '[LocalSend ARM64 build/runtime evidence](evidence/framey-localsend-arm64-2026-10-26.md) '
        'covers an isolated real-Frame protocol 2.0 info response from an earlier helper build. '
        '[Exact official source matching](evidence/framey-localsend-source-match-2026-10-27.md) '
        'now identifies the official helper source and a reproducible ARM64 build from that revision. '
        'The exact official x86 backend passed one local private-namespace transfer, and the rebuilt ARM64 helper passed one locked real-Frame private marker transfer. '
        'Published Decky 3.3.0 AMD64/ARM64 runtime checks discovered the adapted plugin and read its stopped status and configuration. '
        'Only the exact managed 0.4.5 archive can replace its x86 helper on Frame. '
        'The actual managed Decky service on Frame, user-facing transfer, local discovery and worn VR remain unverified '
        '([managed adaptation evidence](evidence/framey-localsend-managed-2026-10-27.md)).', '',
        '[Emuchievements managed helper evidence](evidence/framey-emuchievements-managed-2026-10-29.md) '
        'records the pinned upstream source, bounded archive extraction, no-shell Python invocation and byte-for-byte offline rebuilds for amd64 and ARM64. '
        'Published Decky 3.3.0 on amd64 and ARM64 discovered the exact managed plugin and hashed private synthetic direct and ZIP ROMs while rejecting hostile archives. '
        'The exact ARM64 helper separately hashed private synthetic direct and ZIP ROMs under the real Frame shared lock without waking the headset or changing services. '
        'Only the exact managed 2.0.5 archive can receive the replacement; old installed copies still have the x86 helper and remain broken until update or reinstall. '
        'Real ROM formats, RetroAchievements login, Steam UI integration, real Frame managed backend, and worn VR remain unverified.', '',
        '[Wine Cellar 0.2.1 managed bridge evidence](evidence/framey-wine-cellar-bridge-2026-10-29.md) pins the official ZIP, an ARM64 Rust helper and a receipt-bound fixed-origin WebSocket facade. Published Decky 3.3.0 AMD64 and ARM64 discovered the managed plugin and read an empty private Steam-home state; a separate local Chromium fixture rendered the official empty-state panel with mutating commands denied. Exact-head fake-Frame e2e passed managed install/remove, receipt shim and ARM64 helper/managed Python hash assertions; it did not run the plugin backend. Tool downloads, install/removal, live Steam library, real Frame managed service and worn VR remain unverified. Older copies still contain the x86 helper and need update/reinstall.', '',
        '| Plugin | Native payloads | ARM64 result / remaining blocker |', '| --- | --- | --- |']
    for p in data['plugins']:
        if p['native']:
            binaries = [n['file'].removeprefix(p['folder']+'/') for n in p['native']]
            if len(binaries)>5:
                binaries = binaries[:5]+[f"… {len(binaries)} total; full list in JSON"]
            lines.append('| '+' | '.join(map(cell,[p['name'],binaries,p['nativePort']]))+' |')
    lines += ['', '## Evidence and maintenance', '',
        'The canonical JSON contains full archive hashes, native paths, source URLs, frontend observations and fake-Frame outcomes. '
        'Store compatibility is advisory except known installation/hardware blockers; removal always remains available. '
        'A panel retains its compatibility reason after the initializer reports ready. Upstream fixes require a new digest-scoped audit. '
        'Do not mark a plugin works based on archive installation, fake backend replies or initializer completion.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    output = ROOT/'docs/framey-compatibility.md'
    expected = render(json.loads((ROOT/'ui/framey-compatibility.json').read_text(encoding='utf-8')))
    if args.check:
        if not output.exists() or output.read_text(encoding='utf-8') != expected:
            raise SystemExit('Compatibility documentation differs from canonical store data')
    else:
        output.write_text(expected, encoding='utf-8')


if __name__ == '__main__':
    main()
