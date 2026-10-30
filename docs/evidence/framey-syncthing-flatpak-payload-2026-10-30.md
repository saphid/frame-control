# Syncthing signed Flatpak payload preflight, 30 October 2026

Syncthing 0.2.7 (official store ID 64) remains **broken and blocked from
installation**. This audit advances the actual package gate; it does not
establish Flatpak launch, service behavior, gamescope or Frame usability.

## Exact published app payloads

Flatpak remote-info resolved these Flathub stable commits for
`me.kozec.syncthingtk`. The original HTTPS repository descriptor and its public
signing key are pinned by SHA-256 in the verifier. Both signed commits bind the
expected app, architecture and `org.flathub.Stable` collection and declare the
architecture-matching GNOME 49 runtime.

| App architecture | Exact commit | Packaged Syncthing binary SHA-256 |
| --- | --- | --- |
| x86_64 | `2be395a769ce7f1d8332892c1777d9f1f147ce7f66647864d87d5550e7061034` | `04a55cdd8087653ea148b1c49049eaf4972f308b7b0e5a2bdf3968d37c440ef7` |
| aarch64 | `b5116b67092a6d3bdeb202a0308c2d2ec8f53b980e75e88992781a01aa8937c0` | `5c340f530c0259b41509cd6b511bbcaa910f1553917a896add9830e4e10e602e` |

The [JSON evidence](framey-syncthing-flatpak-payload-2026-10-30.json) records
source/image fingerprints, validity counts, complete content checking and
negative controls. Each architecture has 678 file entries and 380 unique file
content objects. The shared downloaded closure is about 22.6 MB; OSTree checked
495 objects across both commits with no integrity errors. There was one valid
Flathub signature per commit.

Both **packaged manifests** declare the Syncthing **1.27.3** source archive,
SHA-256 `3fe25b863bb3a0f74bc95a7afa71bdaa2a79971542962236be5d85f469aa897d`.
This strengthens the earlier source-manifest observation to signed package
content evidence. No extracted executable was run, so it does not establish
an executable's reported version or behavior. The existing two-peer/service
fixtures use Syncthing 2.1.7 and a launcher shim; their results do not prove this
Flatpak package works.

## Verification and refusal

The downloader bounds each object to 64 MiB, the complete cache to 256 MiB and
its object/directory traversal counts. It preserves the public cache for the
next package test. Downloads alone are explicitly unverified.

The verifier runs as UID 1100 in a networkless, read-only container with all
capabilities dropped and no host bus, home or device mounted. It imports only
the descriptor's pinned Flathub public key into a temporary repository. It
requires libostree's `require_valid_signature()` and a positive valid-signature
count, then checks the entire signed app trees with
`ostree fsck --all --verify-bindings` before inspecting manifests and binary
architecture/digests.

A negative control exposed that `ostree show --gpg-verify-remote` can return
**exit 0 for a BAD signature**. Its status is not a signature-validity gate.
Swapping the two commits' detached signatures is rejected by the validity API
on both architectures. Flipping a byte in the private copied binary content
object makes fsck fail; restoring the copy makes it pass again. The published
input cache is mounted read-only and remains unchanged.

The first container-based network pull returned HTTP 403 for the x86_64
commit and a missing-summary-ref error for aarch64. Direct HTTPS object fetches
on the host succeeded. Offline verification then established both exact app
payloads without disabling TLS, GPG verification or sandbox protections.
This does not establish why those network paths differed.

## Repeat the audit

The download host needs Python GI/GLib and HTTPS access; the verification image
contains libostree's GI bindings. `.github/workflows/syncthing-flatpak.yml`
fetches the exact published app objects and repeats the offline verification
and all negative controls on the PR's exact head. It retains JSON artifacts.
It does not execute either packaged binary.

```sh
/usr/bin/python3 scripts/framey-fetch-syncthing-flatpak.py --directory /path/to/public-cache
docker build -t framey-flatpak-audit:local -f tests/decky-runtime/Containerfile.flatpak tests/decky-runtime
docker run --rm --network none --read-only --user 1100:1100 \
  --cap-drop ALL --security-opt no-new-privileges \
  --tmpfs /tmp:rw,mode=1777,size=512m \
  --mount type=bind,source=/path/to/public-cache/objects,target=/objects,readonly \
  --mount type=bind,source=/path/to/public-cache/flathub.flatpakrepo,target=/input/flathub.flatpakrepo,readonly \
  --mount type=bind,source=/absolute/repo/scripts/framey-verify-syncthing-flatpak.py,target=/verify.py,readonly \
  framey-flatpak-audit:local /verify.py --objects /objects --descriptor /input/flathub.flatpakrepo
```

## Service evidence and remaining gates

The loaded-definition refusal change in #468 passed all 14 checks at
`445ef5b1b93f28f73cf7432123f97c734ca1643f` before merging as
`fc92d73f1122438ff1ae746ce58fe9dd00d278cd`. The pre-merge main passed all 11
checks. Both native artifacts were independently matched to exact committed
sources, helper/build/Decky/runtime hashes, eleven Rust tests, real ownership,
two-way sync and all 17 actual systemd results. Each fixture preserved the
replacement processes through all 18 rejected override/alias controls. This
is AMD64/ARM64 service evidence for the uninstalled candidate, separately from
the static package audit.

Next, pin and verify the matching **runtime payloads**, then launch the actual
app through Flatpak in an owned disposable VM with its default sandbox and
private data. Require actual package service control and two-way sync before
using that result toward compatibility. Managed install/update/remove,
existing-service migration, browser controls and real Frame/SteamVR/controller
gates remain pending. No headset was contacted, no host Flatpak store changed
and no app was installed. Private containers and only the images created by
this audit were removed; public cached objects were retained.
