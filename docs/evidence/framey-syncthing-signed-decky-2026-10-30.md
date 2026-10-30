# Signed Syncthing package through Decky service controls, 30 October 2026

Syncthing 0.2.7 (official store ID 64) remains **broken and blocked from
managed installation**. The prior candidate service fixture exercised real
Decky 3.3.0, systemd and Syncthing 2.1.7 behind an explicit Flatpak launcher
shim. The separate [package gate](framey-syncthing-native-package-2026-10-30.md)
exercises the published signed package, which actually contains Syncthing
1.27.3. Passing these separately did not prove their integration.

## Combined gate

The package VM now accepts an optional candidate helper and its build report.
It requires the current source archive, patch, Python backend and owned-unit
source hashes, the matching native ELF/digest and executed native unit tests.
It independently verifies the published plugin ZIP digest and Decky 3.3.0
loader before packing the guest. No candidate executable is committed,
published or enabled in the managed installer.

After the existing package/signature/sync lifecycle checks, the same
networkless VM runs the actual Decky loader and candidate backend. The helper
creates its real owned user unit with `/usr/bin/flatpak`; no launcher shim is
present. The fixture obtains the package's actual default configuration path
through `syncthing --paths`, generates configuration there without `--home`,
then uses that same default for the candidate unit. The separate private peer
also runs the signed package. The 1.27.3 generator does not accept the 2.1.7
fixture's `--no-port-probing` option.

Flatpak moves the application into a transient application scope. The first
combined run reached Decky REST and the actual package but correctly failed
the fixture's assumption that the application stayed in the service cgroup.
That failed result and console are retained. The probe now binds the live
Syncthing executable to systemd's actual `MainPID` through its parent chain,
records the launcher/application cgroups, checks the executable SHA-256
against the installed package, and requires a distinct mount namespace and
the exact signed app/runtime metadata from that process. Registration or
REST version output alone cannot establish this process identity.

The combined run retains all 17 existing lifecycle requirements and all 18
refusals across foreign drop-ins, shadow fragments and loaded aliases. Those
refusals must preserve the running process, owned bytes/receipt and enabled
legacy marker. Positive controls exercise authenticated Decky REST, API-key
rejection, exact two-way sync bytes, stop/restart, enable/disable and transition
to a separate explicitly selected user service. Certificates and sync data
must survive the transition and data-preserving Flatpak uninstall. The guest
must reap its watchdog and peers and leave no owned Flatpak instances.

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

The prepared native package workflow builds the candidate independently on AMD64
and ARM64 and supplies it to this combined gate. The original shim-mode service
workflow remains a separate regression check and continues to report
`flatpakPackageVerified: false`. Exact-head workflow/source artifacts and
failed results are retained. A new workflow definition or an older package
artifact does not establish a passing combined result on the new head.

## Evidence and admission limits

Earlier in this work, the original shim-mode regression passed locally with
actual systemd/Decky and all 18 ownership refusals; stop completed in 0.338
seconds. Its intermediate fixture source hashes are retained. Its owned VM,
export container and audit-only imported image were cleaned up. Focused tests
cover stale-source/wrong-architecture helpers, incomplete lifecycle/refusal
proofs, different running binaries/commits and compatibility with the oldest
Python used by the checks job.

The [retained JSON](framey-syncthing-signed-decky-2026-10-30.json) records a
passing AMD64 combined run, checked against every current probe source hash,
plus three failed development trials and their cleanup. The passing run
requires all 17 lifecycle results, all 18 ownership refusals and eight process
identity observations. Owned stop took 0.172 seconds and the transition to the
separate user service took 0.967 seconds. Its certificate and reverse-sync bytes
survived uninstall, no owned Flatpak instances remained and its QEMU was reaped.
Seventeen focused tests pass. The server suite during this work ran 1,817 tests
with 16 platform/environment skips and no failures.

The actual default configuration was
`~/.var/app/me.kozec.syncthingtk/.local/state/syncthing/config.xml`.
This fixture explicitly supplies setup settings and the generated private API
key for RPC tests; it does not exercise the setup wizard's config discovery,
migration or browser controls. Those paths must be checked separately.

This follow-up remains a local checkpoint while base PR #472 retries its
failed ARM64 package installation with bounded TCG budgets. The prior AMD64
native package-only artifact passed independent verification; the prior ARM64
artifact proved signatures/content but failed before installation completed.
Native combined AMD64/ARM64 CI remains unverified. Older package-only artifacts
and this local AMD64 result do not establish that new combined native gate.
Merge the base timeout changes and validate the resulting sources before
publishing this follow-up; do not start overlapping native CI while the base
gate is pending.

QEMU exposes no host filesystem, bus, disk, hardware or network NIC. The
published Flatpak's `filesystems=host` permission sees only the disposable
guest. Every legacy unit and data marker used here is newly created by the
fixture; this does not prove migration of a person's existing service/data.
Managed install/update/remove and migration, Frame Control browser controls,
gamescope and real Frame/SteamVR/controller checks remain separate gates.
This work does not contact the real Frame or change the hourly worn schedule.
