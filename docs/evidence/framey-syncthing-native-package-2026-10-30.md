# Syncthing native package gate, 30 October 2026

Syncthing remains **broken and blocked from managed installation**. The
[AMD64 package audit](framey-syncthing-flatpak-runtime-2026-10-30.md) proves
actual package launch, private service control and two-way sync locally.
This follow-up makes the same gate repeatable on native AMD64 and ARM64 CI.
A new workflow definition is not a passing runtime result. Native package CI
remains unverified until the exact-head artifacts prove every required gate.

## Exact signed inputs

`scripts/framey-prepare-syncthing-flatpak.py` pins both architecture-specific
app commits from the existing signed-payload verifier and both matching
GNOME 49 runtime commits from the runtime evidence. The original Flathub
repository descriptor and public key remain pinned by SHA-256.

The fetch phase walks only the expected commit closures, bounds object bytes,
closure bytes, object count and directory/content traversal, validates metadata
checksums and refuses unsafe/oversized seed objects. It uses the existing
bounded transient retries with normal TLS verification. Existing public seed
caches are read only; the new closure goes into a new directory. Download
reports explicitly do not claim payload integrity or package launch.

The bundle phase runs in a private networkless container with read-only
published inputs. It requires the expected refs/collection, valid signatures
through libostree's validity API, then complete
`ostree fsck --all --verify-bindings` before producing bundles. The generated
bundles retain the original signed commits and pinned embedded key. Their
SHA-256 values are recorded as **locally generated bundle hashes**, not hashes
of published Flathub bundle downloads. Regenerating a bundle can change its
outer digest even when the signed target commit and size are unchanged; the
prepared manifest records each generated file and the guest rechecks the
pinned signed commit independently. No content is resigned.

```sh
/usr/bin/python3 scripts/framey-prepare-syncthing-flatpak.py fetch \
  --architecture aarch64 --directory /path/to/new-public-closure
```

Run the bundle phase inside `Containerfile.flatpak-bundles` with the closure
mounted read only, the scripts mounted read only, a private writable output
parent and no network. It creates a new output directory with `app.flatpak`,
`runtime.flatpak`, `flathub-key.gpg` and `preparation.json`:

```sh
python3 scripts/framey-prepare-syncthing-flatpak.py bundle \
  --architecture aarch64 --directory /path/to/read-only-closure \
  --output /path/to/new-bundles
```

## Native runtime gate

The VM wrapper selects the matching QEMU emulator and Debian kernel for the
**host's native architecture**. It checks the preparation report's architecture,
exact commits, key digest, valid-signature counts and full-content result,
then rehashes every input bundle. The guest independently requires the exact
embedded public key and target commit, installed signatures, origin GPG
verification and the expected installed app/runtime commits. Preparation
reports alone cannot establish package execution.

The guest runs the actual signed package with the default Flatpak sandbox
and no user overrides. The published app grants `filesystems=host`; those
paths refer only to the disposable guest. QEMU exposes no real-machine
filesystem, devices, bus or network NIC. Its peers
use new private data and loopback-only transport. It requires the packaged
version and distinct mount namespace, exact forward/reverse synced bytes,
API authentication rejection, actual user-service stop/restart, retained
certificate/data, post-restart sync, owned cleanup and preserving uninstall.
The wrapper checks that guest and host architectures agree and rejects any
missing required result, forced cleanup, source/input change or failed VM.

```sh
python3 scripts/framey-test-syncthing-flatpak-package.py \
  --rootfs-tar /path/to/private-native-rootfs.tar \
  --bundles /path/to/new-bundles \
  --key /path/to/new-bundles/flathub-key.gpg \
  --preparation /path/to/new-bundles/preparation.json \
  --output /path/to/new-evidence-directory
```

`.github/workflows/syncthing-flatpak-package.yml` runs these phases separately
on `ubuntu-latest` and `ubuntu-24.04-arm`, checking out the exact PR head. It
retains fetch/preparation/result/console artifacts plus exact-head source
fingerprints even when an earlier phase fails. Each job must complete
successfully; cancelled, skipped or failed jobs do not prove native package
behavior. Existing Decky/candidate service CI remains separate and uses its
explicitly documented launcher shim.

## Current evidence and limits

Twelve focused tests pass locally: existing transport retry/refusal cases,
changed-descriptor/wrong-ref/unsafe-cache rejection and prepared-input cases for wrong architecture, commits, signature
counts, key, incomplete verification, missing bundles and size bounds.

The [local JSON evidence](framey-syncthing-native-package-2026-10-30.json)
records complete preparation for both architectures and an AMD64 replay using
newly generated bundles and the committed native wrapper. Both app/runtime
signatures are valid on each architecture. The complete ARM64 closure checked
19,639 OSTree objects across two commits with no integrity errors.

The AMD64 prepared-package replay passed installation, exact installed commits
and signatures, enabled origin GPG checks, package version/namespace, two-way
sync, API rejection, actual service restart, retained certificate/data,
post-restart sync, owned cleanup and preserving uninstall. Its service stop
completed in 0.215 seconds. The exact preparation/source/rootfs/kernel/initrd/bundle
fingerprints and all required results are retained. Its owned VM was reaped;
both offline containers and only the image created for this audit were removed.
Public caches and pre-existing data remain. ARM64 bundle preparation on this
AMD64 host is static evidence only; native ARM64 runtime remains unverified.

Native ARM64 package execution is not established by an AMD64 run, ARM64
metadata/downloads or cross-building an image. Even successful package CI
does not establish Framey managed install/update/remove, migration from a
pre-existing service, Decky/browser integration, gamescope, real Frame,
wearer-visible SteamVR panels or physical controller interaction. Those
remain separate admission/release gates. No real Frame is contacted by this
workflow; the separate hourly schedule owns headset checks.
