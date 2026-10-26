# Running-game context and Discord Status, 2026-10-26

Framey now projects running apps and the selected main app from Steam CEF into
detached `SteamUIStore` / `DFL.Router` getters. It relays actual Steam lifetime
callbacks while the panel is open. Public Steam CDN capsule URLs are projected
for running apps; local artwork paths and URL query data never cross the bridge.
The [machine-readable evidence](framey-running-context-2026-10-26.json) records
the exact archives, fixtures, browser observations and cleanup results.

| Plugin / scope | Result | Verification |
| --- | --- | --- |
| Discord Status 1.5.0 | **Broken → partial.** Disconnected panel renders; activity construction accepts the synthetic running game without the previous missing-store/artwork errors. | Exact unmodified official frontend in opaque Chromium iframe; backend/network denied. Actual official `is_connected` returns false in real Decky 3.3.0 ARM64, with no Discord IPC present. |
| Pause Games | **Partial.** Running-list initialization reaches `pid_from_appid` for the synthetic game. | Local Chromium fixture; all backend calls, including settings writes and process actions, denied. |
| Notebook | **Works for its previously verified default notebook scope.** Per-game context is now supplied, but real per-game selection remains unverified. | Synthetic game causes the official frontend to request `loadPage`; backend calls denied in this pass. Earlier default save/reopen ARM64 evidence remains separate. |
| PlayTime | **Partial.** Running snapshots do not satisfy its private MobX observation. | Local Chromium explicitly logs that its running-app observer is unavailable. No automatic tracking claim. |
| 14 other focused panels | Labels retained. Initialization alone does not establish backend functionality. | Exact frontends with synthetic nonempty running/library snapshots and backend/network denied; Game Sync still stops on the denied `get_config` read. |

The bridge addresses a shared dependency detected in 34 official frontend
bundles, including hardware-inapplicable plugins whose installation remains
blocked. This is infrastructure coverage, not 34 working plugins. Catalog after
this pass: **3 works / 49 partial / 53 broken / 11 N/A**.

## Real Frame checks and cleanup

Every device probe acquired the atomic `/tmp/frame-test.lock` and released only
its matching owner. Read-only probes verified the actual RunningApps and
MainRunningApp getter implementations, the lifetime API's object with an
`unregister()` method, and a public `https://shared.steamstatic.com` capsule URL.

A private removable user service ran the published Decky 3.3.0 ARM64 executable
and the exact unmodified Discord Status 1.5.0 store archive. Production
`framey_panel.call_method` returned false from `is_connected`. Production
`poll_running` verified two empty running-list reads, an actual lifetime
subscription and explicit close. The device had no running apps: **nonempty
reads and launch/exit callbacks were not observed on hardware**. Decky startup
reinjected its frontend/restarted Steam CEF. No plugin game, power, audio or process-control
action was invoked, and no Discord connection/activity mutation was allowed.

After close, CEF reported zero sessions and a null timer. The test service,
unit and private base were removed. A fresh independently locked audit read
`LoadState=not-found`, `ActiveState=inactive`, `MainPID=0`, absent paths and zero
CEF sessions/timers. Battery stayed **99 → 99**; normal Decky stayed failed and
the normal panel service stayed inactive. No headset wipe or system service
installation was used.

## Local verification and limits

- Full current official store fetch: 116 IDs/versions/digests unchanged at
  2026-10-26 05:18:22 UTC.
- Fake Frame: 116 transport cases, 60 install/remove cycles and 56 expected
  blockers; private Compose project and volumes removed. Plugin execution was
  stubbed.
- Full local Chromium sweep: 103 of 116 initializer-ready with explicitly
  synthetic library/running data. No backend/network request was allowed.
  The focused Discord Status observation lasted eight seconds and constructed
  `Test Running Game` activity; the visible UI correctly remained disconnected.
- Node contract tests cover actual-event queue projection, retry/deduplication,
  bounds, expiry, unregister, reconnect, update-before-callback ordering,
  invalid data, public-artwork filtering, stale sessions, overlapping reads,
  failure clearing stale state and late replies after close. Nonempty app rows
  and launch/exit notifications in these tests are explicit synthetic fixtures.

The queue retains at most 64 real notifications per session; overflow can lose
old callbacks. Polling runs about every two seconds with no overlap. At most four
CEF sessions survive; unreachable cleanup expires after 15 seconds, checked
every five seconds. The bridge does not implement private MobX internals,
suspend/input events, game actions or closed-panel automation.

Discord shortcut detection, real IPC connection/activity, local custom artwork,
actual running-game transitions, worn VR and physical controller/keyboard use
remain unverified. None of the new fixture checks promotes a plugin to works.

After #301 merged, running polls and both close paths adopted its pinned SHA-256
receipt guard. Local Python/Node tests verify the parent carries that receipt,
missing/stale receipts are rejected before CEF after plugin replacement, and a
reopened panel can poll and close with the new receipt. Rejected stale closes
retain the tested finite-lease cleanup. This authorization-only follow-up did
not repeat the device checks above; their recorded hardware scope is unchanged.
