# Syncthing Flatpak runtime gate, 30 October 2026

Syncthing 0.2.7 (official store ID 64) remains **broken and blocked from
installation**. This follows the [signed app audit](framey-syncthing-flatpak-payload-2026-10-30.md).
It advances runtime-content verification and records a failed disposable-VM
installation. It does not establish package launch, Framey service control,
Decky/browser controls, gamescope, VR or controller usability.

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
reported failure and was reaped. The locally retained experimental harness is
fingerprinted in JSON; it is not a committed or CI-executed runtime fixture.

No TLS/GPG check, bubblewrap sandbox, kernel security setting or OSTree
free-space protection was disabled. Failed attempts are retained, and no pass
is inferred from the valid downloaded payload. No app binary was launched.

## Next gates

Resolve the isolated Flatpak installation failure without weakening security,
then require real package launch and two-way sync through actual service
control. Repeat the complete runtime/package test on native ARM64. The existing
candidate service fixtures use a launcher shim and Syncthing 2.1.7; those passes
do not prove this signed Syncthing 1.27.3 package works.

Framey managed install/update/remove, existing-service migration, browser
controls and the locked real Frame smoke/worn visual/controller checks remain
pending. No real Frame was contacted. Only owned test processes, containers
and images were cleaned; public cached objects and pre-existing data were
preserved. The compatibility rating and installer block stay unchanged.
