# SteamGridDB native backend, 30 October 2026

The exact official SteamGridDB 1.8.1 archive (store 36, SHA-256
`e84f5b1f111af8862b06218479491fbf61036e1bfd9f16f93f9901e9b9ebc5e0`)
passed local AMD64 discovery and 14 API1 RPCs through the pinned published
Decky 3.3.0 loader. The backend, frontend and compatibility policy are unchanged.
The container has no network access beyond loopback, devices, host Steam or
session mounts; its root is read-only and its user home is disposable.

[Source-bound results](framey-steamgriddb-native-2026-10-30.json) cover the
private user-home path, file/base64 bytes, a settings object containing a false
value, saved settings bytes and reads across a full loader restart. Artwork
tests exercise both local-file and loopback-HTTP paths. A private binary
shortcuts fixture verifies signed-ID normalization, set/same-path/clear and
preservation of an unselected shortcut. Both cache paths replace their temporary
files and retain the supplied bytes. Three loopback downloads succeed; the
HTTP worker stops. The host independently reconstructs saved settings and
artwork digests and confirms no owned native-test containers remain.

All three runtime-coverage tests and five official fixture tests pass. Fresh
PR CI must still establish ARM64 runtime and full regression results. This is
backend evidence: the frontend remains broken on unavailable Steam library
context-menu internals. The external artwork service, actual Steam cache
consumption, browser controls, real Frame visuals and physical controller
interaction remain unverified. No compatibility status changes, headset access
or release occurred; the separate hourly headset schedule remains unchanged.
