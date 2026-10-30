# Syncthing candidate setup entry in Chromium, 30 October 2026

Syncthing 0.2.7 (official store ID 64) remains **broken and blocked from
managed installation**. The candidate backend's native service checks do not
establish that its published frontend can reach setup.

## Reproduced blocker

The exact published archive is SHA-256
`27e47379c280c92253d5533435f57c33b332b215f866d2ac4493daf18ec0d1c4`.
Its unmodified frontend awaits service state before reading settings. The
candidate correctly refuses a state read before any owned managed unit exists.
The frontend then retries initialization without ever reading the incomplete
setup settings. Chromium remains on “Loading…”; the fixture caps the observed
requests at 100. There is no usable Start Setup button in this case.

The [legacy migration fixture](framey-syncthing-legacy-migration-2026-10-30.md)
already records the actual helper's missing-unit refusal. This browser test
replays that response synthetically; it does not run a helper or service.

## Uninstalled frontend candidate

`ui/vendor/syncthing-0.2.7/frontend.patch` loads settings first. Profiles whose
setup is incomplete show the published Welcome/Start Setup UI without asking
for service state. Completed profiles still request actual state and display
its failures. The native ownership guards and refusal behavior are unchanged.
The patch is not applied by the installer and does not enable the candidate.

The browser runner checks the exact archive digest and applies the patch with
zero fuzz in a new private temporary directory. It renders through the actual
Framey panel/host and React assets in an opaque iframe. CSP denies network
connections; the parent supplies only finite, synthetic legacy RPC responses.
The browser uses an owned temporary profile and is reaped after each run.

## Verified scope

The [source-bound JSON](framey-syncthing-browser-setup-2026-10-30.json) records
checkpoint `1847e2346aa25b886e3147190aadd12076892ef8`, Chrome
156.0.8078.79 and all six runtime source fingerprints for each observation:

- The unmodified frontend reproduces the missing-unit/loading failure.
- The fresh candidate reaches Installation Method, selects Syncthing GTK,
  completes start/port/API-key/basic-auth scans, changes autostart and the
  desktop toggle, saves completed setup, and reloads watchdog settings. The
  recorded calls must contain the exact scan/reload route sequence and finish
  with saving `is_setup=true` before reload.
- A migrated profile with a retained fixture API key and port reaches setup
  using only settings reads; neither credential nor port changes.
- A configured profile displays the state-500 error with bounded reads rather
  than hiding it or displaying a stopped/running success state.

These are synthetic DOM clicks/change events in Chromium, not physical pointer
or controller input. The [image](framey-syncthing-browser-setup-2026-10-30.png)
shows the fresh wizard's Finish page. Get Started/back navigation, remaining
installation choices, cancellation, live folders/devices and real backend
integration with these browser controls remain unverified.

The earlier probe's button locator omitted the word “the” and failed before
selecting an installation method. That development failure is identified
separately and contributes no wizard pass.

The dedicated browser workflow checks the exact PR head, reproduces the
published failure, runs the three candidate cases and retains source-bound
reports/screenshots. Its presence is not proof of a successful CI run; native
and browser CI for this follow-up remain pending.

The record separately includes independently verified AMD64 combined signed
package/Decky CI from #475 at `67188e1`. That backend proof and these synthetic
browser passes do not establish a combined browser/backend pass. ARM64 browser
execution, managed install/update/remove, gamescope, real Frame visuals and
physical controller use remain separate gates. No real Frame was contacted;
the hourly worn schedule is unchanged and no release is included.
