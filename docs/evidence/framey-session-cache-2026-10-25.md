# Framey session cache browser check, 25 October 2026

Frame Control v0.4.34's opaque Framey iframe made the official Steam Status
1.2.3 frontend log `SecurityError` for its `localStorage` cache. This follow-up
used a per-panel memory substitute. It did **not** change the iframe's sandbox
flags or give plugin code Frame Control's UI key.

A local Chromium page loaded the unmodified official Steam Status 1.2.3 archive
from `tests/fixtures/framey-official/123.zip` (SHA-256
`9053308e04a74f44745b45b9f4f50af3673348d367e7b14bacc5677de707ac4e`).
The page used `sandbox="allow-scripts allow-popups"` and returned `{}` for
four `get_settings` calls. That reply was a stub, not the Decky backend.

The iframe sent `framey:ready`. Its test script wrote and read a cache item.
The parent could not read the iframe document (`contentDocument` was null).
The plugin displayed Steam Status, Store, Community, WebAPI, Connection
Managers and Players Online. Its public status request returned HTTP 200.
No cache `SecurityError` appeared in the captured console, while the
same archive had logged that error with the v0.4.34 host.

Node host tests also checked item updates, removal, clear, key order, string
conversion, quota rejection, and preservation of an existing item after a
rejected write. The substitute keeps at most 256 items and 512 KiB of keys and
values **in memory**. Closing or reloading the panel loses this cache. This
check did not test offline behavior, persistent plugin settings, a live Decky
backend, SteamVR visibility, controller input, or headset performance.
