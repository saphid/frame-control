# Syncthing Flatpak runtime gate, 30 October 2026

Syncthing 0.2.7 (official store ID 64) remains **broken and blocked from
installation**. This follows the [signed app audit](framey-syncthing-flatpak-payload-2026-10-30.md).
It verifies signed runtime content and actual AMD64 Flatpak package launch,
private user-service control and two-way sync in a disposable VM. Framey
managed installation, Decky/browser integration, gamescope, VR and controller
usability remain separate gates. This page records the initial AMD64 audit;
subsequent [native package CI](framey-syncthing-native-package-2026-10-30.md)
verified package execution on AMD64 and ARM64.

## Matching signed runtime

The app metadata requires `org.gnome.Platform` branch `49`. The exact runtime
commit metadata was checked offline with the pinned Flathub public key using
libostree's `require_valid_signature()` and a positive valid-signature count.
Both commits bind the expected architecture-specific runtime ref and
`org.flathub.Stable` collection. Neither declares end of life in this snapshot.

| Architecture | Exact GNOME 49 commit | Verified scope |
| --- | --- | --- |
| x86_64 | `2bb946ea4ebb050f6a32f90e979feb975b08280d1ff1aac881dec3d1361ad84d` | Signed metadata and complete content |
| aarch64 | `c3daeced6f88f9c4ffc4f88c798c48fffd395d873fc0d36b7fc73b753d7f59c9` | Signed metadata only; complete runtime not downloaded or executed |

There was one valid signature per runtime commit. The AMD64 download traversed
2,769 distinct directory trees and fetched 16,410 file-content objects,
403,208,504 object bytes. Downloads were limited to 64 MiB per object, 512 MiB
for the cache, 20,000 directory pairs and 30,000 file-content references.
Downloads alone were not accepted as verification.

The AMD64 runtime and previously verified app objects were assembled into an
offline repository. `ostree fsck --all --verify-bindings` checked 19,664 objects
across three commits with no errors. The AMD64 app and runtime signatures were
checked again before producing local bundles that retain the published
signatures. Nothing was resigned.

The [JSON evidence](framey-syncthing-flatpak-runtime-2026-10-30.json) includes
runtime bindings, source fingerprints, full fsck output, bundle digests and
separate results for failed VM attempts. The runtime bundle is 292,381,368
bytes, SHA-256 `26f36945d6d1af6de730ff6cd62868781d9ed0f99b977b2400101c6f14ce649b`;
the app bundle is 9,872,560 bytes, SHA-256
`5ff38521358f7bb9fefbe7cc4c48c552c3a11290a2f2fa84c69ef70678644977`.

## Installation gate

The probe uses an owned, disposable AMD64 QEMU TCG guest with Debian trixie,
Flatpak 1.16.6, systemd and a private UID 1100 user bus. It has no network NIC,
host disk/home/session bus or headset devices. The signed bundles and pinned
public key are its only package inputs. Install uses:

```sh
flatpak install --user --assumeyes --noninteractive --no-deps --no-related \
  --gpg-file=/input/flathub-key.gpg --bundle /home/tester/input-runtime.flatpak
```

The intended follow-on gates require the installed exact commits and retained
signatures, the packaged executable's reported version, actual Flatpak mount
namespace, private two-way sync, real user-service stop/restart and uninstall
that preserves owned test data. None is credited when installation fails.

The initial fixture omitted input files because of overlay order. The next
attempt hit OSTree's default 500 MB minimum free space; the guest filesystem
was enlarged instead of lowering that protection. A third attempt exposed
bubblewrap's inability to pivot from the fixture's initramfs root. A normal
private tmpfs root via `switch_root` removed that error, but Flatpak then
segfaulted during runtime installation in `libgobject-2.0.so.0.8400.4`.

A diagnostic run retained a GDB stack: the main thread crashed through
`g_type_check_instance_is_fundamentally_a`, `g_object_unref` and
`g_list_free_full`. Its final verbose output attempted to load the embedded
update-origin summary URL in the networkless guest. This was an observation,
not a demonstrated root cause.

The bundles were rebuilt **without an update-origin URL**, retaining the same
signed commits and public key. The completed outputs were rehashed after an
owned report-file write failed; the wrapper's failed exit was retained. The
new runtime bundle is 292,381,320 bytes, SHA-256
`9e2a88bf95d9a6bdcf15335d967ef2d311946875d241b24f998631bdb1899069`;
the app bundle is 9,872,520 bytes, SHA-256
`25c3368e362634e6cf239bc58663bb8b7ca69b6f5fbfa90ab3b86956c1884a04`.

A fresh guest using those bundles still returned **exit -11 (SIGSEGV)** while
installing the runtime, before the exact-installed-commit or retained-signature
checks. Removing the update URL did not resolve the crash. Its root cause
remains unconfirmed; neither app installation nor launch is credited. The VM
reported failure and was reaped. The experimental source and failed run are retained separately from the
repository probe described below.

No TLS/GPG check, bubblewrap sandbox, kernel security setting or OSTree
free-space protection was disabled. Failed attempts are retained, and no pass
is inferred from the valid downloaded payload. Those failed attempts did not
launch the app.

## Resolved extra-key cleanup crash

Debian debug symbols with the same ELF build ID,
`aefb455637ce5753dea536eb90be4b4bd2f37ebf`, resolve the captured application
frames to `bundle_data_free` and `flatpak_transaction_finalize`. The matching
Flatpak 1.16.6 source stores the explicit extra key in a `GBytes`, then calls
`g_clear_object` on it during transaction cleanup. The JSON records the debug
information and source hashes. This explains the observed extra-key cleanup
crash; removing the origin URL alone did not remove that path.

The working fixture uses Flatpak's standard **embedded bundle key** path. It
first requires the entire exact bundle digest, normal-form OSTree delta
metadata, the expected target commit and the embedded public key's exact
SHA-256. It omits the redundant `--gpg-file` argument, leaves each origin's
`gpg-verify` enabled, and independently verifies each installed commit using
libostree with the pinned public key. No signature check or sandbox protection
is disabled, and no Flatpak binary is patched. Both installed commits match
the pinned signed payloads; there are no user Flatpak overrides.

The first launch run reports **Syncthing v1.27.3**, the expected app/runtime
commits in `/.flatpak-info`, and different inside/outside mount namespace IDs.
It then fails on a fixture flag borrowed from the 2.1.7 shim tests:
`generate --no-port-probing` is unsupported by this package. That failure is
retained and does not count as a service or sync pass.

## Actual package service and sync

Removing that unsupported fixture flag allows the full experimental AMD64
package run to pass. Both peers execute the installed package through actual
Flatpak, with new private configuration/data in the guest and only loopback
transport. Discovery, relay/NAT use, telemetry, upgrades and browser opening
are disabled in those new test configurations. API authentication and peer
certificates remain enabled.

The probe requires exact forward and reverse file bytes, an unauthenticated
REST response of 403, actual systemd user-service MainPID, stop to MainPID 0,
a different PID after restart, retained certificate/data and successful sync
after restart. The experimental service stop completed in 0.226 seconds.
It then removes only its fixture unit, reaps both owned peers without forced
termination, requires no remaining package instances and uninstalls the app
without deleting the owned data marker. The VM powers off and is reaped.

This unit is a **private package fixture**, not the Framey ownership candidate
or managed installer. The existing candidate service tests use a launcher shim
and Syncthing 2.1.7; their native AMD64/ARM64 passes remain separate evidence.

## Repeatable repository probe

`scripts/framey-test-syncthing-flatpak-package.py` repeats the package gates
using the committed guest probes and the shared service-VM packer. The original
proof below uses Linux AMD64, Python 3.11+, QEMU TCG, a disposable rootfs export and the exact
bundles/key recorded above. The shared packer supports an ordinary guest root
for bubblewrap; existing shim fixtures retain their previous initramfs path.
No host filesystem is extracted or ownership changed.

`tests/decky-runtime/Containerfile.flatpak-vm` builds the guest rootfs with
systemd, UID 1100, Flatpak, OSTree GI bindings and a Debian kernel. Export a
new stopped container to a private tar file, then remove only that container
and the image created for the audit. A retained export is reusable; its full
SHA-256 is recorded for every probe. The bundles are derived offline with
`flatpak build-bundle --arch=x86_64 --gpg-keys=/input/flathub-key.gpg`, adding
`--runtime` for the GNOME runtime, from a verified OSTree repository with the
exact refs/commits above. Do not add an update URL. The wrapper refuses any
bundle/key digest that differs from the audited inputs.

```sh
python3 scripts/framey-test-syncthing-flatpak-package.py \
  --rootfs-tar /path/to/private-rootfs.tar \
  --bundles /path/to/audited-bundles \
  --key /path/to/flathub-key.gpg \
  --output /path/to/new-evidence-directory
```

The wrapper refuses an existing output directory, retains failure JSON/console
logs, enforces a 960-second VM limit and checks every required result before
success. QEMU has 6 GiB RAM, two virtual CPUs, no NIC, host disk/home/bus or
headset devices. A marked guest bootstrap is required before any service or
shutdown command. Nineteen ownership/transport/guard tests passed locally,
including refusal of the package bootstrap on a host with UID 0 mocked.
The original package proof was a manual runtime test. The
[native package follow-up](framey-syncthing-native-package-2026-10-30.md) adds
exact-head AMD64/ARM64 package CI; its presence is not a passing result.

The repository runner passed all required gates on AMD64. Its full JSON and
exact source/rootfs/kernel/initrd/bundle fingerprints are recorded separately
from the experimental pass. It stopped the service in 0.184 seconds,
retained the certificate and synced bytes after restart, removed its unit,
reaped all owned processes/VM and preserved its data marker after uninstall.
These results are local runtime evidence; package execution is not claimed
from ordinary CI.

## Remaining gates

Repeat complete runtime installation and package/service/sync verification on
native ARM64. Then connect this actual package to the Framey ownership
candidate and test managed install/update/remove, existing-service migration
and Decky/browser controls. These package results do not admit Syncthing to
the managed installer or improve its compatibility rating yet.

The locked real Frame smoke/worn visual/controller checks remain pending.
No real Frame was contacted. Only owned test processes, containers and images
were cleaned; public cached objects and pre-existing data were preserved.
Release v0.4.56 is unchanged.
