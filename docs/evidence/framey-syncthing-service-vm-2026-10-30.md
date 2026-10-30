# Syncthing actual service-manager preflight, 30 October 2026

Syncthing 0.2.7, store ID 64, remains **broken and rejected by the managed
installer**. The exact published archive digest is
`27e47379c280c92253d5533435f57c33b332b215f866d2ac4493daf18ec0d1c4`.
This fixture tests the uninstalled candidate; it does not bundle an executable
or contact the real Frame. Release v0.4.56 is unchanged.

## Actual failure and fix

The preceding ownership change passed native AMD64/ARM64 Decky and private
runtime tests in #466, but its container had no actual systemd user manager.
The new service VM supplied that manager and exposed a real timeout: switching
from a running managed Syncthing to a selected external service stopped the
managed process normally in about ten seconds. The candidate's ordinary
five-second HTTP timeout expired first, returning `timed out` through Decky.
The guest journal showed TERM at 05:47:40 and normal exit at 05:47:50.

Only POST setup/start/stop/reload lifecycle calls now receive a 20-second socket
budget, within the host panel's existing 25-second RPC budget. Reads and scan
probes keep five seconds. Route/header restrictions, private socket ownership,
response bounds, four worker slots, API keys and TLS are retained. Regression
coverage includes a real delayed reload response and checks both socket budgets.

## Fixture and proof

`scripts/framey-test-syncthing-service.py` exports a disposable Debian Trixie
image with its public Debian kernel. It creates a guest-only newc initramfs
directly from tar metadata, retaining guest UID/GID without extracting or
changing ownership of host files. QEMU runs unprivileged with TCG, two CPUs,
2 GiB memory and no NIC, shared host filesystem, disk, device or session bus.
No privileged container or host cgroup/security change is needed.

The guest runs actual systemd PID 1, an actual UID 1100 user manager and DBus.
A successful transient user unit confirms that the bus can execute jobs.
The exact published Decky 3.3.0 loader discovers the plugin, and legacy RPC
controls the candidate's private socket and real user-manager service jobs.
Two pinned real Syncthing v2.1.7 peers use new private configs and loopback-only
addresses. Discovery, relays, NAT, telemetry, upgrades and browser opening are
disabled only in these new configs. API keys and TLS certificates remain.

The service probe requires all of these results before writing success JSON:

- The owned unit and exact-byte receipt agree, and actual systemd resolves the
  expected user-home fragment.
- A running Syncthing has the expected executable, real MainPID and service
  cgroup; REST version reads travel through actual Decky RPC.
- Both peers independently receive the expected forward and reverse file bytes.
- Stop finishes inside the panel RPC budget, the unit is inactive and its real
  process is reaped. Restart retains the synced bytes, certificate and marker.
- Actual enable/disable symlinks target the owned unit. The pre-existing private
  legacy fixture remains enabled/running with its original PID and file bytes.
- External-service transition stops/removes only the proved owned managed unit
  and receipt, retaining its persistent lock and private runtime files.
- Explicitly selected external-service start/stop controls another real
  Syncthing process through its real user-service cgroup.
- Owned peer/backend/helper processes are reaped. The VM powers off and is
  reaped; the wrapper removes its container, temporary filesystem and only the
  image it built. An explicitly provided image is preserved.

The bootstrap rejects execution outside the marked owned guest **before** any
service, journal or shutdown commands. A regression exercises this rejection
even with UID 0 mocked, requiring no subprocess calls. Before VM setup the wrapper
removes any prior success JSON and rejects missing/ambiguous/incomplete results
or source changes during execution. Failure retains the console log.

The [local machine-readable report](framey-syncthing-service-vm-2026-10-30.json)
records the architecture, actual manager/kernel, image/kernel/initrd digests,
exact source/helper/loader/runtime fingerprints and every completed result.
The earlier prepared-image AMD64 run completed the formerly failing external
transition in **10.697 seconds**. The final fresh repository-image run passed
all required results, stopped the first managed process in **0.357 seconds**
and completed the external transition in **11.381 seconds**. Its owned image
was independently confirmed absent after cleanup. ARM64 service-VM execution
remains pending CI; AMD64 TCG execution
is not an ARM64 result. Both native CI jobs must execute this new service probe
alongside their existing filesystem, ownership and runtime tests, with JSON and
console artifacts retained. A cancelled, skipped or failed job is not a pass.

Local Python coverage passes 18 ownership/transport/guest-guard tests,
16 compatibility contracts and 30 panel tests. No browser test was added or
claimed by this service-manager fixture.

## Remaining limits

The `flatpak` command is an explicitly checked **launcher shim** executing the
real pinned Syncthing binary. The actual Flatpak package and package ownership
remain unverified. The published archive is still refused by the installer.
Managed install/update/remove, service drop-ins/aliases/overrides and migration
from existing user services remain pending. Loading the expected fragment in
this clean fixture does not prove behavior with arbitrary overrides.

Browser rendering/controls, gamescope session behavior, real Frame runtime,
SteamVR wearer-visible panels and physical controller interaction are also
unverified. No wake, input, hardware lock or headset operation occurred here;
the separate hourly worn-check schedule keeps ownership of that check. Nothing
in this evidence admits Syncthing, changes its compatibility rating or satisfies
the release's locked real Frame smoke gate.
