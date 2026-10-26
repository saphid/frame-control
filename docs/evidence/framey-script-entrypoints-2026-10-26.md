# Executable script entrypoints: Junk-Store

Junk-Store 1.1.13 (official ID 84) moves **broken → partial**. The exact unmodified
BSD-3-Clause archive is pinned in the [redacted results](framey-script-entrypoints-2026-10-26.json).
No ARM64 rebuild or upstream plugin source patch was needed.

Python ZIP extraction drops execute permissions. This archive also publishes its
shebang scripts as 0644, relying on upstream Decky's recursive permission setup.
Framey's user service disables that setup. Direct script calls therefore fail.
The installer now adds **owner execute only** to shebang scripts or ZIP-declared
executables. It does not restore archive privilege/write bits, grant group/other
execute, or change unmarked data permissions. Archive validation and installation
blocks remain in place. Existing installations need update/reinstall for repair.

The upstream comparison is Decky 3.3.0's
[permission setup](https://github.com/SteamDeckHomebrew/decky-loader/blob/v3.3.0/backend/decky_loader/browser.py)
and [Linux implementation](https://github.com/SteamDeckHomebrew/decky-loader/blob/v3.3.0/backend/decky_loader/localplatform/localplatformlinux.py).
Static inspection found 28 accepted official archives with shebang or declared
executable members. This is shared installer coverage, not 28 functional claims.

## Before and after in an isolated real backend

Both runs used the exact official plugin and published Decky 3.3.0 amd64, with no
network/devices/capabilities, a read-only root and private temporary home/tmp.
The only difference was the production installer before/after this change.

| Check | Before | After |
| --- | --- | --- |
| `scripts/get-json.py` | 0644 | 0744 |
| `execute_action(init, init)` | inner `Type:Error`, empty output / JSON parse error | `Type:Success`, `Initialized` |
| `execute_action(init, InitActions)` | inner `Type:Error` | `Type:ActionSet`, `MainMenu`, four actions |

The legacy wrapper reports `success:true` even for the failing inner error.
Startup log text alone is also insufficient: the baseline emits initialized/started
messages despite those errors. Both private containers were removed.

## Real ARM64 Frame and local Chromium

Under the shared headset lock, the patched production installer installed the
official archive into a private, bounded, removable Decky 3.3.0 ARM64 user service
on Frame OS 0.5.6. The service was not enabled. Legendary was absent before and
after; no dependency installer, login, download, launch or websocket command ran.

The production receipt-bound bridge called the actual backend through live Steam
CEF. Static action sets, main-menu content and the Epic action set returned real
results. `get_websocket_port` returned 8765. Explicit `init/init` success was tested
in the isolated amd64 backend; it was not explicitly invoked in the final Frame run.

Local Chromium ran the actual Framey host and official frontend in an opaque
iframe, relaying only allowed static calls to that ARM64 backend. Main menu,
Games → static Epic tab, Back and fresh close/reopen passed. Steam library reads
used the production receipt-bound bridge; only counts were retained. Outer
status/install responses were fixtures, and the deployed headset HTTP endpoint
was not tested.

The About route still crashes on missing `local_per_client_data.installed` in
the detached app overview. Epic game-list and RSS calls were deliberately denied;
their loading/error views do not demonstrate backend failure. Dependency
installation, login, game operations, RSS, Steam shortcut mutation and worn VR
remain unverified. This supports **partial**, not works.

Three temporary attempts were cleaned, including an initial Steam reinjection
readiness failure and a test-relay omission of the library endpoint. A fresh
shared-lock audit found all three services inactive/unloaded (PID 0), with their
private bases, unit files and archives absent. Normal managed Decky/panel services
stayed inactive; final battery was 99 → 100 while charging. No power-setting action
ran. The audit lock was released, and local relays/browser tabs were closed.

## Verification

- Python suite: 1,628 tests, 16 skipped, no failures; store suite: 19 passed.
- Site suite: 18 passed. Two new regression tests failed before the fix.
- All 116 official plugins: fake-Frame 60 installed/removed, 56 expected blocks;
  no actual plugin backends run by this harness. Disposable project cleaned.
- Fresh official-store audit: 116 plugins, zero errors; ID/version/digest set
  matches the catalog. Other plugin statuses are unchanged.
