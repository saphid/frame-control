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
shows the fresh wizard's Finish page at the initial checkpoint. Remaining
installation choices, cancellation, live folders/devices and real backend
integration with these browser controls remain unverified.

The earlier probe's button locator omitted the word “the” and failed before
selecting an installation method. That development failure is identified
separately and contributes no wizard pass.

## Completion navigation follow-up

A further source-bound trial at `d993f5d` clicked Get Started after Finish. The
route returned to the plugin, but the published delayed call to
`Navigation.OpenQuickAccessMenu(QuickAccessTab.Decky)` raised an uncaught error:
the isolated panel has no Steam quick-access menu API or tab enum.

The candidate now uses its existing NavigateBack route without that Steam-menu
call. At checkpoint `af4d98e8ffe429fff7943697322810aa431ce16e`, all five cases
passed independent fingerprint/cleanup checks: the expected published setup
failure, fresh setup, migrated entry, configured-state failure, and wizard
completion/navigation without browser errors. The fixed frontend SHA-256 is
`6abfd4861c74f730f9d29d00bfc478e8967f9f56c4ea84a442aac41a0d62972f`.

The completion case deliberately returns the synthetic state-500 response
after navigating back. It verifies that the configured error UI is reachable
and the unavailable Steam call is gone; it does not prove a running service or
combined browser/backend behavior. Both the failed trial and final cases are
retained in the JSON. No host-wide menu API or native ownership guard changes.

## Manual port fallback

The ARM64 backend trial in #475 failed its first port-scan assertion. The
published frontend actually performs one port scan and offers manual entry
when it returns null. Bounded native fixture retries do not exercise that UI.

At checkpoint `df46f0f634313fc3ad68d1c4f1a7ef389982e02a`, a new synthetic
browser case returns a null scan result. Chromium displays the published
manual port instructions, accepts DOM input of **8390** instead of the initial
8384, saves that exact value through the host bridge, completes setup, and
returns to the configured error view without browser errors. The recorded
call sequence contains exactly one port scan; it cannot pass by silently
retrying discovery or accepting the default port. All six source fingerprints
independently match the committed checkpoint; the browser was reaped.

This report is included in the JSON. Its screenshot shows the final synthetic
configured-state error, not the manual port field. The selected port and API
key are fixture values and were never tested against a real backend. First
scan readiness, combined browser/backend behavior and physical controller
interaction remain unverified.

The dedicated browser workflow checks the exact PR head, reproduces the
published failure, runs the five candidate cases and retains source-bound
reports/screenshots. Its presence is not proof of a successful CI run; native
and browser CI for this follow-up remain pending.

The record separately includes independently verified AMD64 combined signed
package/Decky CI from #475 at `67188e1`. That backend proof and these synthetic
browser passes do not establish a combined browser/backend pass. ARM64 browser
execution, managed install/update/remove, gamescope, real Frame visuals and
physical controller use remain separate gates. No real Frame was contacted;
the hourly worn schedule is unchanged and no release is included.

The migration layer #476 passed all 15 checks at
`7a84502e01feb6a7a5f9f82c4ce27693577a2b8a` and merged as `af0433b`.
Its AMD64 and ARM64 signed-package artifacts were independently bound to that
exact source, signatures, signed process identities, 12 migration results,
nine setup results, 17 lifecycle results, 18 ownership refusals and retained
data after uninstall. The JSON retains both artifact IDs/digests and summaries.
ARM64 needed two null backend probes before discovering 8384. Those backend
fixture probes do not prove that the published UI retries; the synthetic
manual-port case above still exercises its actual single-scan fallback.
This additional native backend proof remains separate from browser execution.

## Exact-head browser CI

The dedicated Chromium workflow 41048089800 passed for #477 at
`8b01a614b865ac9469f4a6fa7cc0605ebc31ab07`. Independent audit of artifact
12973481694 binds its GitHub artifact digest, five exact-head metadata source
hashes and all six runtime source hashes in each of its six cases. The
[source-bound summary](framey-syncthing-browser-setup-ci-2026-10-30.json) retains
case result and screenshot hashes, Chrome version, request counts and ports.
All six captures were visually inspected: Loading for the original, Finish
for fresh setup, Installation Method entry for migration, and the expected
configured-state error for configured/completion/manual-port cases. The manual
port is established by the recorded input/save sequence and port 8390, not by
the final error capture. Browser cleanup is verified for every case.

The negative original result is the workflow's required reproduction; all
five candidate cases pass. This records the browser job only, not completion
of #477's remaining native/e2e/main gates. All responses here remain synthetic;
actual browser/backend integration has its separate disposable-VM record.

The separate native ownership workflow 41048089307 also passed on this exact
#477 head. Both architecture artifacts were independently checked against
their GitHub digests and every reported source fingerprint. They show actual
Decky discovery, owned helper lifecycle, two-way Syncthing **2.1.7** sync, actual
systemd control, 17 service results and 18 ownership refusals. These artifacts
do not use the signed Flatpak 1.27.3 package. That separate AMD64 job in
41048089270 failed waiting for the forward sync file after 90 seconds. Its
failure is retained; #477's merge gate remains closed.

The exact #477 ARM64 signed-package artifact 12976035575 also passed independent
audit of its GitHub digest, all source hashes, signatures, actual signed
identities, lifecycle/migration results and preserving uninstall. Backend port
discovery needed three null scans before 8384; it remains separate from the UI.
The failed main and #477 AMD64 artifacts have identical hashes for all 13
native runtime inputs but failed at different fixture stages. That comparison
does not establish the sync timeout's root cause. The pending follow-up adds
an explicit real peer-connection gate and retains its observed state before
checking transferred bytes. The failed AMD64 result still holds #477's merge.

The later refreshed head `ff663a7` passed fresh browser, ownership and signed
AMD64/ARM64 gates and merged as #477. The [refreshed exact-head evidence](framey-syncthing-setup-ff663a7-ci-2026-10-30.md)
records both native artifact audits and the final merge gate. The older
failed head above remains a failed result; its cause was not established.
