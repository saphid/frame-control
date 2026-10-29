# Decky Notifications private panel display, 29 October 2026

The official Decky Notifications **1.0.1** frontend ZIP was read from the pinned
fixture and independently matched SHA-256
`3b22dc337209615f91da566ceb968793dc163b2e509de8535fb5d0fc55817312`.
Its unchanged frontend ran in Framey's opaque local Chromium iframe through
`scripts/framey-audit-browser.py --decky-notifications-fixture`. The fixture
replied with one synthetic trusted phone and one synthetic notification; its
content did not come from a phone, the real Frame or the native backend.

The panel reported ready with no errors or console warnings. Chromium displayed
**Trusted Devices**, the private test phone, **Recent Notifications**, the
fixture alert title and body, and a Clear control. The frontend requested
`device_list`, `notification_list` and `get_event`; no denied method was
requested during this display check. [Captured panel screenshot](framey-decky-notifications-panel-2026-10-29.png).

The browser fixture's CSP blocked external network access, and its RPC handler
denied trust, clear and other backend writes. The Clear control was not pressed.
The separate [native backend check](framey-decky-notifications-2026-10-29.md)
used actual Decky 3.3.0 in isolated containers, but this panel was not connected
to that backend. Phone pairing, LAN delivery, real Frame backend operation,
wearer-visible VR and physical controller use remain unverified. The plugin
stays **partial**.
