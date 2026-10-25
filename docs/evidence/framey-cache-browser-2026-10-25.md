# Framey cache check, 25 October 2026

The official Steam Status 1.2.3 ZIP pinned in
`tests/fixtures/framey-official/123.zip` was loaded through Framey's local
HTTP panel in Chromium. The iframe retained `sandbox="allow-scripts
allow-popups"`, so its native storage remained unavailable. The new Framey
storage facade accepted a set/get probe without a `SecurityError`. Steam
Status rendered and issued four `get_settings` calls to a stub parent backend.
Its `steamstat_last_status` cache entry was about 33 KiB, below the bridge's
128 KiB cap. After reopening the iframe, the parent supplied the saved cache
snapshot and the plugin wrote the same cache key again. The browser log had
zero `SecurityError` or `localStorage` errors.

The parent was a local test page with in-memory Decky backend replies. One
public status fetch also failed in the test browser, so this check does not
establish offline correctness or the freshness of Steam Status data. The
per-plugin save/reopen protocol, stale panel session rejection, and cache
limits are covered by `tests/page/framey_cache.mjs`. Frame OS persistence,
live Decky settings, VR visibility, and controller input remain unverified.
