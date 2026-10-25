# Steam Status in the local Framey browser, 25 October 2026

This check used the unmodified official Steam Status 1.2.3 archive already
pinned in `tests/fixtures/framey-official/123.zip`. Its SHA-256 is
`9053308e04a74f44745b45b9f4f50af3673348d367e7b14bacc5677de707ac4e`.
The archive declares Decky API v2. No headset was contacted for this check.

On a Linux PC, we extracted the archive to a disposable plugin folder with a
Frame Control store receipt. A local HTTP server served the page from
`framey_panel.panel(123)`, Frame Control's React 18.3.1 runtime and its
`framey-host.js`. A parent page put the panel in an iframe with
`sandbox="allow-scripts"` and returned `{}` for the plugin's `get_settings`
backend calls. This was a **stub**, not the Decky service.

Chromium reported `framey:ready` and four `get_settings` calls. The page showed
Steam Status, Store, Community, WebAPI, Connection Managers, Players Online,
and other controls. Its own public `https://steamstatus.schelstraete.org/api/v1/status`
request returned HTTP 200 and populated the status view. A click on **Refresh**
sent Framey's trusted pointer event to the parent; this test did not prove a
fresh status fetch or settings write. The [browser screenshot](framey-steam-status-browser-2026-10-25.png)
contains only the local test page and public service data.

The plugin logged `SecurityError` while reading and writing `localStorage` in
the opaque-origin iframe. It caught the errors and rendered anyway. Its cache
and offline behavior in Framey are **not verified**. The real Decky backend,
live settings, SteamVR visibility, controller input and headset performance
were not tested. This result supports only local frontend rendering for this
exact archive and Frame Control v0.4.34 host code.
