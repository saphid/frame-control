# Storage Cleaner shutdown after an IPC peer closes

The AMD64 runtime gate for #605 head
`bde8e15b6e9f146ef59ed8d0056f05fb9e93c121` failed on Storage Cleaner 1.4.0.
Its private cache deletion RPCs succeeded, but Decky forcibly killed the plugin
five seconds after requesting shutdown. This is a runtime failure, not another
dependency-download failure. The [producer job](https://github.com/saphid/frame-control/actions/runs/42470323140/job/128862223419)
uploaded artifact `13634338460`; its ZIP digest, exact checkout, console digest
and 50 source bindings were independently verified.

Exact managed installs of archive ID 50, SHA-256
`1afa1a6f129c5d419de0e0bf0f6db8d8e50385a5659179346e996031ea372591`,
now receive the existing child-local IPC EOF adapter in addition to the
bounded-deletion repair. A closed peer ends that connection's read loop instead
of repeatedly dispatching empty input. The parent loader and other plugins keep
their original transport. No stop deadline is extended. Existing installations
need Update/reinstall.

A deterministic native AMD64 probe closes an owned Unix socket peer before
signaling only the loader. Before the repair it failed the clean-stop assertion:
Decky killed the plugin after five seconds. With the repair, two loader-only
stops completed in 0.235 and 0.215 seconds without forced termination or shutdown
errors. Restart discovery and a read RPC passed between stops. Exact descendant
identities were reaped, private cache markers remained byte-identical, and an
unrelated sibling survived. Storage Cleaner has no original unload hook; none
is claimed to run.

The negative control removes only this new adapter, checks the previous bounded
backend's exact digest, and reproduces the five-second forced kill. It retains
the safe deletion adaptation and is explicitly not compatibility evidence. Its
container has a CPU/memory cap to contain the original EOF spin; the repaired
positive uses the normal strict runtime policy. All execution is in disposable
network-isolated Docker containers with private cache data and the digest-pinned
published Decky 3.3.0 loader. The 101 focused store/runtime/IPC tests passed
without skips, including refusal to install without the offline adapter.

The [local receipt](framey-storage-cleaner-ipc-eof-2026-11-08.json) binds the
tested sources, raw report digest, backend and adapter digests, positive stops,
and expected negative. Fresh full hosted AMD64/ARM64 qualification is pending.
This child-process reproduction does not establish the historical ARM64 parent
migration timeout's cause or clear the release hold. Locked exact-release Frame
smoke, real Steam cache changes, worn VR and controller input remain unverified.
No headset was contacted. Storage Cleaner's compatibility rating stays partial.
