# Static limits for two official Decky archives, 28 October 2026

The published archives below were downloaded from Decky's version CDN and
checked against the catalog's exact SHA-256 before inspection. No plugin code,
backend, plugin-initiated network request or headset operation ran in this
audit. Their status labels remain unchanged.

## IsThereAnyDeal for Deck 1.1.1

Store ID 81, SHA-256
`18e133b2e6203f16fd1ee2ed83b5a90bad34491515bef7ec1c82d525f0bfadef`.
The backend exposes settings load/save. The published frontend uses
`fetchNoCors` for deal lookups with an embedded upstream API key and attempts
to find a Steam store debugger tab through `localhost:8080/json`. The key was
not decoded or used. The existing real Frame country read and local settings
render remain the verified scope; live deals, settings writes and Steam page
integration remain unverified. Status stays **partial**.

## Decky Clipboard 1.0.1

Store ID 119, SHA-256
`d283bd9a5c35b3fac3788391736a6763f3e8c4615831a7c560c9fa6e6c0950ac`.
The manifest requests root and the ZIP bundles an x86-64 `bin/xclip`. In the
published `main.py`, `auto_start` defaults to true; `WebServer.start` binds
`0.0.0.0:8765`, and the clipboard GET/POST routes have no authentication
check. A managed adaptation would need to address that behavior before any
Frame install. The archive remains **broken** and was not installed or run.
