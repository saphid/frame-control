# API v1 panel check, 25 October 2026

The unmodified official Storage Cleaner 1.4.0 archive (store ID 50, SHA-256
`1afa1a6f129c5d419de0e0bf0f6db8d8e50385a5659179346e996031ea372591`)
declares `api_version: 1`, but its bundled frontend connects to Decky's modern
frontend API. Framey admitted that bundle from a local store receipt and
rendered it in Chromium inside an iframe with `sandbox="allow-scripts
allow-popups"`.

A test parent returned empty lists and `0B` for the plugin's two list and two
size backend calls. Chromium reported `framey:ready`, displayed Shader Cache
and Compatibility Data sections, and showed all four cleanup buttons disabled.
No cleanup action was invoked. The backend was a stub; the test did not run the
plugin's Python code or connect to a headset.

This confirms a panel shell for this exact archive with empty data. Storage
Cleaner may remove compatibility data and local game saves when used with a
real backend. Its cleanup actions, game names, SteamClient app details, VR
visibility, and controller input remain unverified on Frame. Do not infer that
its deletion controls are safe or complete in VR from this browser check.
