# Chunked Framey frontend audit route, 26 October 2026

The local 116-plugin Chromium audit served chunked modules at a route that
omitted the store receipt, while the production panel requested
`/framey/module/<id>/<receipt>/<file>`. The audit parsed that receipt as part
of the file path and returned 404. This made its result for chunked frontends
weaker than the separate targeted panel checks.

The audit now accepts the production URL shape only when the plugin ID,
receipt and JavaScript path are valid, the receipt equals the catalog SHA-256,
and the cached archive bytes match that SHA-256. Invalid IDs, receipts, paths
and changed archive bytes fail before the module is served. The production
Framey panel and installer are unchanged.

## Exact archived browser check

Pinned official Deck Shelves 2.0.0 (store ID 135, SHA-256
`b566280ad38fd3ecd584b5b46a855f301539eb9a86063834c64b7045f7063f91`)
ran through the repaired audit in an opaque Chromium iframe. Its entry module
and all eight JavaScript chunks returned HTTP 200 at receipt-bound URLs. The
frontend reported ready and called `get_settings`; the audit denied that
backend call and a Steam library read. Plugin network access remained blocked
by the audit policy. The previous
catalog browser observation had failed to resolve `./chunks/...` from a blob
URL. This check verifies the current audit route and frontend initializer,
not the official backend or a live shelf.

The focused route regression covers entry and chunk reads plus wrong receipt,
path traversal, malformed ID and changed archive bytes. The catalog's
**4 works / 50 partial / 51 broken / 11 N/A** statuses are unchanged. Deck
Shelves remains partial; installed settings, home-shelf behavior, worn VR and
physical controller input remain unverified.
