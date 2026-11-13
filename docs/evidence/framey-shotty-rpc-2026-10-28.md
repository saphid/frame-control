# Shotty screenshot copy through native Decky RPC, 28 October 2026

The exact official Shotty 0.1.0 archive (store ID 53, SHA-256
`ab7f6618b264a0cb766525e788cef6c3e1478c0fef98a701225e5e8af441e2fe`)
was installed with Frame Control's digest-scoped `shotty-click-app-dir` shim.
The local `scripts/framey-test-decky-runtime.py` run used the published,
digest-verified Decky 3.3.0 amd64 loader in a disposable unprivileged container
with no network, host devices or writable host mount. Its full 14-case native
suite, including three negative controls, exited successfully.

The Shotty case placed two small marker files under a private synthetic Steam
screenshots directory in the container's temporary home. Calls went through
Decky's real legacy websocket RPC. `set_id_map_fronend` supplied a private game
name; `copy_screenshot` returned `true` for the selected file. Independent
reads of `Pictures/Screenshots/Private Game/selected.jpg` and
`Pictures/Screenshots/most_recent.jpg` matched the marker bytes. A later
`aggregate_all` returned `1`, and the historical file in the named folder
also matched its source bytes. Empty aggregation and `was_rescued=false` still
passed. The runner removed its owned containers and image; no headset or user
screenshot was accessed.

This local run checks the real Decky RPC and same-filesystem copy path with
synthetic files on amd64. The PR's hosted native ARM64 gate must pass before
merge; this local result alone does not establish ARM64 behavior. Steam's live
screenshot notification, cross-filesystem copies, the continuous rescuer, real
Frame installation, wearer-visible VR and physical controller use remain
unverified. Shotty remains **partial**.
