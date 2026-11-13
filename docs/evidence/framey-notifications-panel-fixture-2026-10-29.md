# Decky Notifications 1.0.1 local panel replay, 2026-10-29

Official store ID 79, ZIP SHA-256 `3b22dc337209615f91da566ceb968793dc163b2e509de8535fb5d0fc55817312`.

Run `python3 scripts/framey-audit-browser.py --cache <cache> --decky-notifications-fixture` with the exact ZIP at `<cache>/<sha256>.zip`. This opt-in fixture supplies one synthetic trusted phone and one synthetic notification through the official legacy `device_list` and `notification_list` calls. It replies to `get_event` with no event. Every other backend method, including `trust_device` and `notifications_clear`, is denied. The existing CSP blocks external network, fetch and WebSocket. The exact frontend executes in Framey's opaque local Chromium iframe; its Python backend is not run.

In T3 Chromium, `runAudit([79],1800)` returned `ready: true` with no error or console logs. The panel showed **Private test phone** under Trusted Devices and **[Framey fixture] Private test alert / Local fixture body** under Recent Notifications. Clicking the trusted device opened a local dialog containing Remove device; it was closed without choosing Remove. Clicking Clear sent `notifications_clear`, which the fixture recorded and rejected; no backend data changed. The fixture test verifies the three accepted legacy replies and rejects trust, clear, unknown and modern calls.

This proves local display and dialog construction with synthetic data. It does not prove real Frame backend operation, pairing, LAN delivery, trust changes, notification clearing, live event toasts, physical controllers or worn VR visibility. Decky Notifications remains **partial**.
