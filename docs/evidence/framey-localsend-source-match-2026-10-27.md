# Decky Localsend 0.4.5 source match and ARM64 build, 27 October 2026

The exact official store archive (ID 125, SHA-256
`e271ccb55eb23f918b99a69f79aec905df4c9b2ef7b23bbf4ec1c2d1a6f0c6b7`)
remains **blocked** on Frame: it carries an x86_64 `bin/localsend-core`.
No managed plugin install, transfer, or status promotion was performed.

The archive's `main.py` has SHA-256
`db03f9201fe50b75dea99a7a05b54ec3f352d1bdfe174115b0e569154198d8ad`,
identical byte for byte to `main.py` at the upstream Decky plugin tag `v0.45`
(`7c166bdc33e2a667527ffd511eb5b90d3ce0bd67`). That tag pins its Go
submodule to `ad28b8e9440e17e44b4735a6c4aa0512009cf333`. All 42 dependency
versions embedded in the official helper match that source's `go.mod`, which
declares Go 1.25.7.

Building that pinned Go commit with `CGO_ENABLED=0`, `GOOS=linux`,
`GOARCH=amd64`, and the flags `-trimpath -buildvcs=false -ldflags='-s -w'`
produced **byte-identical** official helper bytes: 15,241,400 bytes,
SHA-256 `d448d03861d578685e6c70ea3ace25eb34fca99cb9d4f98bf51ba23aa5cae843`.
This resolves the source correspondence gap left by the earlier build from
the later `66edc509` commit. The same pinned source and flags with
`GOARCH=arm64` produced a static AArch64 ELF of 11,731,128 bytes, SHA-256
`e20363237e606ee65eae857792176d21a0bb8ba863489952728eaf2b13277dae`.
Two ARM64 builds matched byte for byte. The Go core is MIT licensed; the
separate Decky Python plugin is BSD-3-Clause.

A unique-owner atomic `/tmp/frame-test.lock` preflight on the real Frame read
SteamVR activity **1**, proximity raw **88.0625**, and battery **35%**.
Because the headset was active or wearer status was unknown, the probe did
not upload or execute the ARM64 helper, start a LocalSend service, or send
input. The task-owned directory was absent and only the owned lock was
released. This is **not** a worn visual or controller result.

The unmodified plugin backend's `_main` starts a fixed-path Unix notification
socket but does not start the Go network service. Its explicit `start_backend`
method starts the helper with a default all-interface setting, HTTPS and
auto-save disabled. A safe runtime test must isolate that service and use only
private fixtures. Before a managed ARM64 adaptation, verify actual Decky
backend discovery/RPC, the frontend, and a private transfer; package the
source, license and exact helper digest. The official x86_64 archive remains
blocked until that work passes. Worn VR and physical controller use remain
unverified.
