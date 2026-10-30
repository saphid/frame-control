# Syncthing browser and actual signed backend candidate, 30 October 2026

Syncthing 0.2.7 remains **broken and blocked from managed installation**.
The preceding browser trials supplied synthetic RPC responses; the signed
Decky/package trials separately replayed backend methods. Neither established
that browser controls operate that backend together.

## Combined fixture

The optional `--browser-setup` package probe builds the actual Framey panel
and host with the exact published frontend plus the uninstalled candidate
patch. The guest runs Debian Chromium with its sandbox enabled, published
Decky 3.3.0, the source-bound ownership helper and signed Syncthing 1.27.3
Flatpak with the pinned GNOME runtime. No `--no-sandbox` flag or relaxed
Flatpak override is used. Renderer seccomp/no-new-privileges state and ancestry
to the owned browser are required.

All processes run in one disposable VM with no network NIC, host bus, home,
disk or session exposure. Its private loopback HTTP bridge forwards actual
legacy RPC to Decky. The iframe still has an opaque origin and no network
access. The bridge logs method/route/status and setting names, excluding API
keys, headers and raw credential-bearing responses. This bridge is test code;
it does not exercise the production Frame Control HTTP/SSH transport.

Synthetic DOM input must complete the real setup wizard, return to an actual
running dashboard with the private folder visible, stop, restart and stop the
owned service. At each stage, the fixture cross-checks the actual systemd PID
and signed Flatpak process identity. It retains dashboard screenshots, the
redacted RPC journal and process observations. The verifier requires the
setup/control routes and four lifecycle stages; backend registration or
success flags without these observations cannot pass.

After the browser closes, only this newly created guest profile is reset for
an independent backend scan/lifecycle replay. Existing migration, two-way
sync, ownership refusal and preserving-uninstall checks still run. The guest
and QEMU must be reaped. AMD64 is the only implemented browser architecture;
ARM64 browser, real Frame/SteamVR and physical controller interaction remain
unverified. This is not a managed install/update/remove test.

```sh
python3 scripts/framey-test-syncthing-flatpak-package.py --browser-setup \
  --rootfs-tar /path/to/private-rootfs-with-chromium.tar \
  --bundles /path/to/prepared-bundles \
  --key /path/to/prepared-bundles/flathub-key.gpg \
  --preparation /path/to/prepared-bundles/preparation.json \
  --candidate-helper /path/to/native-build/x86_64.watchdog \
  --candidate-build-report /path/to/native-build/build-report.json \
  --output /path/to/new-evidence-directory
```

The optional rootfs is built with
`--build-arg 'BROWSER_PACKAGES=chromium chromium-sandbox'`. It has a separate
2 GiB guest root and 8 GiB guest memory budget. Only the exact optional
`usr/lib/chromium/chromium` path may exceed the normal 256 MiB entry cap, with
a 384 MiB bound. The input rootfs remains capped at 2 GiB. The existing
non-browser defaults are unchanged.

## Current evidence

The private workflow adds an independent AMD64 browser entry alongside native
AMD64/ARM64 package entries, with exact-head metadata and screenshot artifacts.
It has not run in CI. Workflow YAML and shell blocks parse locally; 24 focused
package/input/evidence tests pass. These are not runtime proof.
The full server suite at `04fcd58` passed 1,837 tests in 223.328 seconds,
with 16 platform/environment skips and no failures.

The first trial at `988c2c1` stopped in the host packer: the Chromium executable
is 331,230,040 bytes and exceeded the normal file bound. No VM launched.
The second trial at `d01472a` was intentionally stopped after source review
found an incorrect test locator: folders/devices add buttons beyond the four
power/navigation toolbar controls. Only its owned QEMU process group was
terminated and reaped. Neither trial contributes a runtime pass.

The third trial at `04fcd58` uses the bounded Chromium exception, selects the
power control inside the exact toolbar, and retains a failure-stage journal.
It failed before readiness, with no completed browser stages or RPC calls.
The owned browser, bridge and VM were reaped. Its parent CSP omitted the
`data:` script source needed by the embedded runtime; the test fixture now
permits those scripts and separately denies all child network connections.
A fresh combined trial remains required. A passing result must be independently
bound to all packed source fingerprints before any completion claim.

A local Chrome readiness regression reproduced the CSP failure with zero RPC
calls. Allowing the embedded scripts reached ready and made two initial
settings calls. This small reproduction used synthetic settings and no sandbox
disable flags; it supplies no actual-backend or Frame usability proof.
The fourth combined trial runs at `86311dc`, with the corrected test-only
parent policy and the explicit child `connect-src 'none'` policy.
