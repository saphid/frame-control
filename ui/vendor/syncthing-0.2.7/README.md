# Syncthing 0.2.7 ownership candidate

This candidate is **not selected by the managed installer**. Syncthing remains
blocked. No candidate executable is bundled or published. The separate native
CI jobs build and test it without exposing host services, devices or a session.

The exact official store archive (ID 64) has SHA-256
`27e47379c280c92253d5533435f57c33b332b215f866d2ac4493daf18ec0d1c4`.
Its original `main.py` SHA-256 is
`87620c3f85a381aa12d2dbee39da3629403e68c2f3ba7294b3693c2cb78e4100`.
The corresponding source is
[upstream v0.2.7](https://github.com/theCapypara/steamdeck-decky-syncthing/tree/464fd7ca05ee0bea8daa8d5d125dfc672cf08942).
The upstream Python bytes match the official ZIP. `LICENSE` retains the original
GPLv3/template/Syncthing notices.

`source.tar.gz` contains the original Rust sources, locked manifest and license;
its SHA-256 is
`a17f1c0bdfa70cf666c0d57a996a25597ac2f4791d43463a5dbf0639a0e51f8f`.
`watchdog.patch` changes startup ownership and adds private HTTP IPC: retain an exclusive file lock,
reserve the fixed listener before settings/PID/log/systemd activity, and remove
PID/executable-name discovery. A private Unix listener shares the original HTTP
handler and uses a socket in the Python owner's temporary directory (0700),
with socket mode 0600. It requires Rust 1.89 or later; builds use 1.98.1.
The service-file follow-up adds `owned_unit.rs` and uses a separate
`frame-control-syncthing.service` in the actual user's home. A matching header
and exact-byte sidecar are required for updates, removal and managed control.
Foreign/edited, symlinked, hardlinked, oversized or wrong-owner files and
unsafe parent directories are refused. A persistent lock serializes cooperating
candidate operations; this is not a sandbox against arbitrary same-UID writers.
Legacy `decky-syncthing.service` files are never automatically adopted or removed.
Managed guards run before DBus, including the wizard's early stop. External
transition stops/disables/removes only a proved owned new unit, and failures
propagate. A reserved managed name cannot bypass ownership in external mode.
A separate networkless service VM exercises actual systemd/DBus, fragment
identity, enable links and explicit external-service control. Drop-ins, aliases,
existing-service migration and actual Flatpak packaging still need verification.
Gamescope, HTTP authentication and TLS code are unchanged.

The candidate `main.py` retains its own `Popen` session until it is reaped,
bounds TERM/KILL waits, and stops it on unload. Restart and v1 migration no longer
invoke name-wide `pkill`/`killall`. A late restart after unload is refused.
PID cleanup takes the same exclusive lock and checks the retained child PID;
it preserves another owner's PID and the persistent lock inode. A typing-only
`NotRequired` annotation is replaced with `Optional` for Python 3.9 importability.
Its HTTP RPC accepts only the published frontend's GET/POST routes and selected
headers, bounds response bytes and socket operations (normally 5 seconds, 20
for setup/start/stop/reload service lifecycle calls), preserves HTTP errors and
does not follow redirects. Four worker slots remain occupied until completion,
even if their RPC awaiters are cancelled. The transport uses only that retained
child's private Unix socket; there is no TCP fallback. Restart/unload removes
the temporary directory only after reaping the owned child.

Build with an existing Rust Bookworm image containing native/ARM64 targets and
compilers, for example the local Wine Cellar cross-builder:

```sh
python3 scripts/build-framey-syncthing.py \
  --image framey-wine-cross-mppkd9qczt:20261029 --fetch \
  --output /tmp/syncthing-candidate-build
```

Fetching uses only the locked public dependencies. Compilation runs offline in
a disposable container with a read-only root filesystem, dropped capabilities,
no devices and only the owned build directory writable. A prepared public
Cargo cache may replace `--fetch` with `--dependency-cache PATH`; only its
registry/git directories are copied, never credential or configuration files.
The output report identifies source, patch, Python, lockfile, image and binaries.

The native CI matrix uses `rust:1.98.1-bookworm` and builds only the runner's
native architecture. The test runner verifies the exact official ZIP and the
published Decky 3.3.0 loader before injecting the candidate into a private home.
This is not a managed-install or Frame test.

An inactive receipt-bound host facade keeps the original frontend's fixed
loopback URLs. Only the exact digest and a dedicated receipt shim may call the
HTTP RPC; no installer currently produces that shim. Node VM coverage verifies
the transport facade, not browser rendering. See the
[private HTTP evidence](../../../docs/evidence/framey-syncthing-http-2026-10-30.md).

A [real-runtime preflight](../../../docs/evidence/framey-syncthing-runtime-2026-10-30.md)
uses pinned upstream Syncthing v2.1.7 test inputs. AMD64 and ARM64 private two-way sync,
runtime restart and actual REST reads through released Decky RPC passed #465 CI;
the processes are started directly, with service setup disabled. The source fingerprints and both native reports were independently checked. No runtime is bundled.

The service preflight boots a private systemd guest using QEMU TCG on the
matching native AMD64 or ARM64 runner. There is no guest NIC or host filesystem,
device or session-bus passthrough. It uses a launcher shim for the `flatpak`
command and the same pinned real Syncthing binary; this does not prove the
actual Flatpak package. Run it with the native helper:

```sh
python3 scripts/framey-test-syncthing-service.py \
  --helper /tmp/syncthing-candidate-build/"$(uname -m)".watchdog \
  --output /tmp/syncthing-service.json
```

Docker and the matching `qemu-system-x86_64` or `qemu-system-aarch64` executable
are required. The runner builds/exports a private Debian guest image and records
its image/kernel/initrd/input digests, then removes only its owned container,
temporary files, VM and newly built image. An explicitly provided `--image` is
preserved. VM failure leaves a console log; prior success JSON is removed before
VM setup.
Both architecture CI jobs must execute the full probe. See the
[service VM evidence](../../../docs/evidence/framey-syncthing-service-vm-2026-10-30.md).

Before admission, verify Flatpak packaging, managed install/update/remove,
unit overrides/migration and browser controls. Automatic gamescope behavior is
not SteamVR behavior. Real Frame and physical controllers remain unverified. See
[`docs/evidence/framey-syncthing-ownership-2026-10-30.md`](../../../docs/evidence/framey-syncthing-ownership-2026-10-30.md).

See the [service-file evidence](../../../docs/evidence/framey-syncthing-service-files-2026-10-30.md)
for the filesystem and pre-DBus proof preceding the service VM fixture.
