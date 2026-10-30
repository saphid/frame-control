# Signed Syncthing legacy profile migration, 30 October 2026

Syncthing 0.2.7 (store ID 64) remains **broken and blocked from managed
installation**. This fixture extends the combined signed-package/Decky gate
with an actual running legacy user service and version-1 settings, entirely
inside a newly created, networkless VM.

## Private legacy service

The fixture generates a fresh Syncthing 1.27.3 configuration, certificate,
private key and retained sync file under `/home/tester/migration-legacy-state`.
It disables discovery, relay and upgrades and uses private loopback ports.
The real signed Flatpak runs under `decky-syncthing.service`, initially enabled
and active. Executable hashes, signed app/runtime commits, mount namespace and
parent lineage bind its monitor/server processes to the actual systemd
`MainPID`.

The published Decky 3.3.0 loader reads version-1 settings from the actual plugin
settings directory. The candidate backend must persist version 2 while
retaining the old API key, port, application and desktop preference, translating
autostart to gamescope and setting `is_setup="migratingV2"`.

Before explicit setup completion, the fixture checks state, start and stop
through actual Decky RPC. No managed unit or ownership receipt may be created;
the live legacy process identities, unit bytes, enabled status, config,
certificate, private key and retained data must remain unchanged. An unrelated
helper-named process must also remain running. State returns 500 because no
owned managed unit exists; normal start and stop return 204 as no-ops while
setup remains incomplete. This refusal is recorded, not described as a
successful service-state display.

## Explicit external-service control

Only after the fixture explicitly selects the existing user service and saves
and reloads completed setup may it control that service. Authenticated REST
must return the expected device identity; a request without an API key must
return 403. A real stop must reap the old signed processes, and a restart must
produce a new systemd `MainPID` with the same signed executable/package proof.
Configuration, certificate, private key and data hashes must remain unchanged.

Cleanup unloads and reaps the fixture's helper, Decky and unrelated sentinel,
then removes only the exact legacy unit created by this fixture. Data remains.
The normal combined fresh-setup/service fixture runs afterward. A preserving
Flatpak uninstall must retain both the migration files and fresh-setup data.

## Recorded evidence and limits

The [JSON record](framey-syncthing-legacy-migration-2026-10-30.json) binds the
local AMD64 replay to checkpoint `3a308783a5fc1c5404b4b9cd5ba2a118d72bbe8d`.
Independent verification checks all 13 packed source fingerprints, 12 migration
results, nine fresh-setup results, 17 lifecycle results and 18 ownership
refusals, along with process identity and preserving uninstall. The owned VM
was reaped. All 21 focused input/evidence tests pass. The earlier full server
run passed 1,833 tests with 16 platform/environment skips, before the final
pending-state assertion correction; it is not an all-platform native result.

One failed development replay is retained. It incorrectly expected state to
succeed before a managed unit existed. The helper correctly refused the
missing unit; the fixture now requires that exact refusal and checks the
legacy service is preserved after every route. The failed VM was reaped and
contributes no passing result.

The record also retains independent package-only AMD64 and ARM64 artifact
audits from main `759468214a4f21700cf184338edb658a7fe675b0`. These prove the older
main package gate, not combined migration CI on this follow-up. Exact-head
native combined CI on both architectures is still required.

This covers a newly created private legacy service and one version-1 profile
with autostart enabled. It does not access or migrate a person's existing data.
Other profiles, wizard cancellation, browser controls, gamescope, managed
install/update/remove, real Frame visuals and physical controller interaction
remain separate gates. The VM exposes no host filesystem, bus, disk, hardware
or network NIC; the Flatpak's host permission sees only that disposable guest.
No real Frame was contacted. The hourly worn schedule is unchanged.
