# LocalSend ARM64 build and isolated Frame probe

The official Decky Localsend archive remains **broken/blocked**: its helper is
x86_64. A source rebuild is now proven to execute on the ARM64 Frame and answer
the LocalSend 2.0 info endpoint. This is a core runtime result, not a working
official-plugin or file-transfer claim. [Machine-readable evidence](framey-localsend-arm64-2026-10-26.json)
records the exact scope and cleanup.

## Reproduce the build

The helper is MIT-licensed; the separate official Python plugin is BSD-3-Clause.
Use the pinned helper source and retain its license for any redistribution.
No binary is redistributed in Frame Control, and no installer digest or
architecture safeguard was changed.

```sh
framey_build_dir=$(mktemp -d)
git clone https://github.com/MoYoez/LocalSend-Go "$framey_build_dir/source"
git -C "$framey_build_dir/source" checkout --detach 66edc509a28b9f877e7374504892dcbc653a4da4
cd "$framey_build_dir/source"
env GOTOOLCHAIN=go1.25.7 CGO_ENABLED=0 GOOS=linux GOARCH=arm64 \
  go build -trimpath -o "$framey_build_dir/localsend-core" .
sha256sum "$framey_build_dir/localsend-core"
```

Two builds produced the same static aarch64 ELF SHA-256:
`e79238f6051ce34f172f765ae918d3d902b819e27377989a55e5b1eba10e46f9`.
The official ELF uses Go 1.25.7 too, but embeds no VCS revision, so the exact
source correspondence is still unproven. The rebuilt helper recognizes every
CLI flag supplied by the official Python backend.

## Real Frame scope

Tests ran under the normal atomic `/tmp/frame-test.lock` with a private temporary
directory. `-h` exited before configuration or networking. For the health probe,
`unshare -Urn` created a private user/network namespace with loopback and a veth
pair entirely inside it: no external interface or default route. The veth used
the documentation-only `192.0.2.1/24` address. Upstream rejects a loopback-only
discovery interface, which is why the second isolated attempt used a veth.

The helper used a private config/upload path, `-skipNotify`,
`-useAutoSave=false`, `-useAutoSaveFromFavorites=false`, `-useHttp=true`,
`-useReferNetworkInterface probe0` and `-scanTimeout 1`. The test client sent only
`GET /api/localsend/v2/info` over loopback; it returned version `2.0`, device type
`headless` and the private test alias. No upload, transfer, pairing or external
discovery request ran. The helper exited; its private config/log and executable
directory were removed; no service or power setting changed. The lock was
released. An independent cleanup reacquisition found another job's lock and
left it alone; cleanup success comes from the original probe's process wait and
temporary-directory exit, not that deferred audit.

Before enabling an ARM64 official package, verify the unmodified Python backend
and frontend/proxy protocol with this source revision, then HTTPS, discovery and
an explicitly safe private transfer. The official store must publish a matching
ARM64 archive or Frame Control must gain a separately reviewed, digest-scoped
build/package path. Compiling the core does not justify accepting the current
x86 archive or marking the full plugin works.
