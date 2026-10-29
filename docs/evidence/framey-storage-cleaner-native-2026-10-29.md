# Storage Cleaner 1.4.0 managed backend, 29 October 2026

The exact official store archive for ID 50 has SHA-256
`1afa1a6f129c5d419de0e0bf0f6db8d8e50385a5659179346e996031ea372591`.
Its `decky-storage-cleaner/main.py` has SHA-256
`6fd4d012568edae22ba421495455b3c02899155e4c7484f5aa5be6ce9b14dd5f`.
The original `delete_cache` awaits synchronous `shutil.rmtree`: a disposable
fixture was deleted, then the method raised `TypeError`. The managed installer
checks both digests before adapting its private copy. It calls `rmtree`
synchronously and accepts only `shadercache`, `compatdata`, or a numeric app-ID
child under either. It rejects traversal and symlink paths. The official ZIP
is unchanged; an already installed managed copy needs Update.

`python3 scripts/framey-test-decky-runtime.py --case 50 --output /tmp/framey-storage-cleaner-native-20261029.json`
passed on native x86_64 with the published Decky 3.3.0 loader. Its disposable
container had no external network, host devices, session bus, or user home.
Decky discovered the official plugin, returned the private fixture's size
and game-list row, deleted one selected shader-cache app directory, then
deleted the whole private compatdata fixture. Both RPCs completed without
the previous error. The 41 store transaction tests passed, including guard
checks for traversal and symlink paths, install receipt, and remove. The
container and image were removed. No real Frame lock or device was used.

The bundled frontend also used `forEach(async ...)` for selected app IDs, so
its confirmation callback completed before those deletion RPCs. A follow-up
managed adaptation for the same pinned archive and frontend digest
`8252cfcd2182546f715cc0e4116a887fcf40af1b8b9d132bd1761c8b9ff46fdb`
awaits each selected deletion in order. A Node test runs the installed bundle's
actual `clearDataCache` function with private deferred RPCs: the promise stays
pending until all selected calls complete, stops on a rejected call, and still
handles whole-directory deletion. This is a callback completion check, not a
visual confirmation or real cache deletion check.

Framey's ConfirmModal now keeps an asynchronous action open until it settles,
blocks duplicate activation and Escape/Close while pending, and displays a
rejected action for retry. The host action test covers both a deferred success
and a rejected private action. This is local host behavior; the actual Storage
Cleaner confirmation has not been visually exercised on the real Frame.

The deletion fixture does not prove real Steam cache cleanup or recovery.
Real Frame ARM64 backend, frontend confirmation flow, worn VR and physical
controller behavior remain unverified. Storage Cleaner stays **partial**;
the compatibility counts do not change.
