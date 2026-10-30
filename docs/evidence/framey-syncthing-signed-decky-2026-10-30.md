# Signed Syncthing package through Decky setup and service controls, 30 October 2026

Syncthing 0.2.7 (official store ID 64) remains **broken and blocked from
managed installation**. Earlier fixtures ran published Decky 3.3.0 against
Syncthing 2.1.7 through a Flatpak launcher shim, while the separate package
gate ran the actual signed Syncthing 1.27.3 package. Those separate passes did
not prove their integration.

## Combined gate

The package VM accepts an optional candidate helper and its build report. It
requires current source archive, patch, Python backend and owned-unit hashes,
a matching native ELF/digest and executed native unit tests. It independently
checks the official plugin ZIP digest and published Decky 3.3.0 loader before
packing the guest. No candidate executable is committed, published or enabled
in the managed installer.

After the existing signature/package/sync checks, the same networkless VM runs
the actual Decky loader and candidate backend. Its owned user unit launches
`/usr/bin/flatpak`; no launcher shim is present. The package itself supplies
its default paths through `syncthing --paths`; its configuration is generated
without `--home`. The separate private peer also runs the signed package.

Flatpak moves the app into a transient application scope and Syncthing 1.27.3
may retain both monitor and server processes. Every matching process must have
the expected executable hash, exact signed app/runtime metadata and a distinct
mount namespace. Its parent chain must reach the actual systemd `MainPID`.
Launcher/application cgroups are retained. Backend registration or a version
response alone is insufficient.

The fixture requires all 17 lifecycle results and 18 refusals across foreign
drop-ins, shadow fragments and loaded aliases. Refusals must preserve live
processes, unit/receipt bytes and the enabled legacy marker. Positive controls
exercise authenticated Decky REST, API-key rejection, exact two-way sync bytes,
stop/restart, enable/disable and transition to an explicitly selected separate
user service. Certificates and sync data must survive that transition and a
data-preserving Flatpak uninstall. Owned watchdogs, peers and Flatpak instances
must be reaped.

## Setup discovery through actual RPC

The actual default config is
`~/.var/app/me.kozec.syncthingtk/.local/state/syncthing/config.xml`.
The setup replay starts with `is_setup=false` and an empty stored API key. It
uses the official start/port/API-key/basic-auth scan routes through actual
Decky RPC, saves discovered settings through the backend, and authenticates
against the running package with the discovered key. It checks the returned
device identity against the private generated configuration.

The published frontend finishes setup by saving `is_setup=true` **and**
reloading watchdog settings. The fixture reproduces that sequence before
checking normal Stop. Its verifier requires all nine setup results, including
remaining unconfigured during scanning, saving/reloading setup and actually
stopping the owned service. Generated API keys and private-key contents are
excluded from evidence.

This exercises the wizard's backend sequence, not its browser controls.
Migration, wizard cancellation/abandonment, non-default credentials and GUI
interaction remain unverified.

```sh
python3 scripts/framey-test-syncthing-flatpak-package.py \
  --rootfs-tar /path/to/private-native-rootfs.tar \
  --bundles /path/to/prepared-bundles \
  --key /path/to/prepared-bundles/flathub-key.gpg \
  --preparation /path/to/prepared-bundles/preparation.json \
  --candidate-helper /path/to/native-build/x86_64.watchdog \
  --candidate-build-report /path/to/native-build/build-report.json \
  --output /path/to/new-evidence-directory
```

The package workflow builds the candidate independently on AMD64 and ARM64 and
runs this combined gate. The original shim-mode workflow remains a separate
regression and reports `flatpakPackageVerified: false`. Both workflows check
out the exact PR head. Artifacts/source fingerprints and failed results are
retained; workflow definitions or older artifacts do not establish a pass.

## Evidence and admission limits

The [JSON record](framey-syncthing-signed-decky-2026-10-30.json) contains the
passing local AMD64 combined setup replay and its independent verification.
All 12 packed source hashes match checkpoint
`9b0074b9b37b8ba690b1a4368a0195f9d34f230f`. All nine setup results, 17 lifecycle
results, 18 ownership refusals and ten process identity observations passed.
Owned stop took 0.160 seconds; transition to the separate user service took
0.994 seconds. Certificate and reverse-sync bytes survived uninstall, no owned
Flatpak instance remained and QEMU was reaped. All 18 focused tests pass.

The earlier combined replay and shim regression remain identified separately.
The server suite during earlier development ran 1,817 tests with 16
platform/environment skips and no failures; 11 RDP tests passed after merging
the base changes locally. These are scoped development results, not native
combined CI proof on a later head.

Five failed development trials are retained: incorrect cgroup/process-count
assumptions in the first three, then two setup fixture mistakes. Normal Stop
is skipped while setup is false; saving setup alone also leaves stale watchdog
settings until the explicit reload. The corrected replay follows the published
frontend's save/reload sequence. Each failed VM was reaped and contributes no
passing result.

Base PR #472 merged after independently verified exact-head package-only CI
on AMD64 and ARM64 at `3fcda28`; see the [native package record](framey-syncthing-native-package-2026-10-30.md).
Those artifacts and the local AMD64 replay do not establish native combined
AMD64/ARM64 CI, which remains pending for this follow-up.

QEMU exposes no host filesystem, bus, disk, hardware or network NIC. The
published Flatpak's `filesystems=host` permission sees only the disposable
guest. Every legacy unit/data marker here is newly created by the fixture;
this does not prove migration of a person's existing service or data.
Managed install/update/remove and migration, Frame Control browser controls,
gamescope and real Frame/SteamVR/controller checks remain separate gates.
The hourly worn schedule is unchanged; no real Frame was contacted.
