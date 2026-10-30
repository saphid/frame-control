# Syncthing loaded service identity, 30 October 2026

Syncthing 0.2.7 (store ID 64, exact published archive SHA-256
`27e47379c280c92253d5533435f57c33b332b215f866d2ac4493daf18ec0d1c4`)
remains **broken and rejected by the managed installer**. This uninstalled
candidate does not bundle an executable or contact the real Frame.

## Reproduced mismatch

The [service VM preflight](framey-syncthing-service-vm-2026-10-30.md) proved
actual systemd service behavior in a clean guest. A separate regression probe
then added a private drop-in that replaced the owned unit's ExecStart with
`/usr/bin/sleep infinity`. The main unit and exact-byte receipt still agreed,
and systemd's FragmentPath still pointed to the expected owned main file.

At head `6d7c10c556bd2b850a06583003208609c71c4753`, the actual candidate
accepted POST stop with HTTP **204** and stopped the private replacement
process: MainPID changed from **359** to **0**. This was an owned networkless
VM fixture, not a host or headset process. The failure demonstrates why the
main-file receipt alone does not prove which loaded service is controlled.

## Change

Before managed state/start/stop, setup's early stop, enable/disable and external
transition, the candidate loads the real manager's unit and reads fresh DBus
properties with proxy property caching disabled. It requires:

- loaded state, the exact canonical managed ID and no additional aliases;
- the exact receipt-owned user-home fragment path;
- no drop-ins and no pending daemon reload.

Existing receipt/file checks and the persistent ownership lock remain held.
Missing/invalid properties and bus errors fail closed. A new unit may be
created only when the manager reports it absent; after writing and daemon
reload the loaded definition must pass before enable/disable. Own install-link
changes finish with another daemon reload and identity check; the expanded
positive lifecycle caught this necessary completion after enable left the
manager reporting a pending reload. Explicit external
service control retains its existing semantics; the managed name stays reserved.

Overrides, aliases, foreign shadow fragments and pending edits are preserved.
The candidate does not remove them, reload them as recovery, adopt them or
attempt to repair their services. These checks are not protection from arbitrary
concurrent same-UID writers between observation and action.

## Verification scope

Eleven Rust ownership/resolution tests pass, including actual private filesystem
preservation and refusal of wrong fragment/ID, additional aliases, drop-ins,
pending reload and non-loaded states. The candidate compiles offline for AMD64
with the unchanged pinned dependencies. Native ARM64 execution is a CI gate;
cross-compilation is not an ARM64 runtime result.

The expanded actual systemd VM fixture replaces the service command with a
private sleep process, tests a higher-priority user.control fragment and a
loaded alias to its private already-running legacy service. It requires state,
start, stop, wizard start, reload and external transition to refuse while
preserving process IDs, unit/receipt/override bytes and the legacy enable link.
A separate un-reloaded drop-in must cause refusal while the real Syncthing
process keeps its original PID. Both the refusal cases and ordinary real
two-way sync and full service lifecycle remain required, with cleanup.

The [machine-readable report](framey-syncthing-loaded-unit-2026-10-30.json)
records the red probe's fingerprints and the corrected build/native/service
results. Both native CI jobs must execute the full fixture, with no failure,
cancel or skip accepted as a pass.

The final local AMD64 helper
`8902ad2f65c73cd1d08888722f9dba070c7486ab01fb1b7fa6a034a3e0446035`
passed actual Decky ownership/restart/reload/private-HTTP tests and all 17
required service VM result flags. All 18 override/alias control attempts
returned HTTP 500. Replacement process IDs remained **362**, **417** and
**291**, respectively. Normal managed stop completed in **10.222 seconds**;
the external transition completed in **10.620 seconds**. Real forward/reverse
bytes, certificates, markers and legacy links survived. The report retains
each actual loaded ID/fragment/drop-in list, rejected route and preserved PID.
The guest powered off and the owned QEMU process was reaped.

The preceding service-only head `81e243b893efb54e527f764978345ac895492c26`
passed all 14 checks, including actual service VMs on both AMD64 and ARM64,
before #467 merged as `aea15ae72e135e74a245dc904bdb7f108df8970e`.
Both artifacts were independently checked against exact committed sources,
helper/build/loader fingerprints, nine filesystem tests, ownership/RPC results,
real two-way sync, HTTP 403/completion 100, all 13 then-required service results
and console output. That proof does not cover this new identity guard on ARM64.

An initial local native-container image build timed out before candidate
execution. The completed native probe can use the explicitly prepared service
VM rootfs image instead: the same native ownership fixture runs as UID 1100
with no network, bus or writable host path. Its report records the immutable
image ID and that the image was provided. The wrapper preserves provided
images; only the caller removes its own image after all probes finish. CI
continues to exercise its normal image build on each architecture.

## Remaining limits

Refusal is the supported behavior for managed overrides/aliases; this does not
provide their migration or adoption. Actual Flatpak packaging and package
ownership remain unverified because the service fixture uses an explicit
launcher shim with the real pinned Syncthing binary. Managed install/update/
remove, existing-service migration, browser controls, gamescope behavior,
real Frame runtime, SteamVR wearer-visible panels and physical controller
interaction remain pending. The installer and compatibility rating stay blocked;
there is no release or hardware operation in this change.

The read-only Flathub source check also found that
[`syncthing.yaml` at `c9920f1d518f5baab73a7f0555eb6836acfa999a`](https://github.com/flathub/me.kozec.syncthingtk/blob/c9920f1d518f5baab73a7f0555eb6836acfa999a/syncthing.yaml)
pins Syncthing **1.27.3**, whereas this fixture deliberately tests pinned
**2.1.7**. This source observation does not establish which package is published
or installed. The package gate must verify an actual pinned Flatpak payload
and its runtime behavior; neither the source manifest nor the v2 binary fixture
satisfies that gate.
