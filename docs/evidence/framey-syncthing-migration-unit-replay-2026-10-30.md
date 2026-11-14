# Clean migration and service-loader replay

The [independently audited local report](framey-syncthing-migration-unit-local-2026-10-30.json)
records the completed isolated AMD64 replay at exact repair head
`6e8f0f9291be2db99862ab1e38b9e9edc1c8f745`. All 124 source fingerprints match.
The complete checksummed guest-result packet contains 1,006,727 bytes; the
owned QEMU process was reaped. This supersedes the earlier successful
package summaries whose retained migration-loader log still contained
cancellation errors, without erasing that historical failure evidence.

The actual signed app/runtime installation, two-way sync, 12 migration checks,
17 service lifecycle checks, 18 ownership refusals, 20 signed process identity
observations and data-preserving uninstall all pass. The migration registry
drained in 0.285 seconds. Both actual Decky units stopped with mixed policy,
inactive/success, exit status zero and MainPID zero. The migration-loader stop
took 2.306 seconds and the service-loader stop 7.64 seconds. Both full loader
logs were checked; the retained console contains no shutdown-error,
CancelledError or pending-task markers.

The production parent made 64 successful HTTP calls and the fixture recorded
72 native CEF RPCs. All eight capture payloads were verified. The five distinct
images were inspected: Running/Stopped/Running/Stopped appeared in both the
private bridge and production parent; the restarted private bridge showed a
folder scan. Representative [parent Running](framey-syncthing-migration-unit-http-parent-running1-2026-10-30.png),
[parent Stopped](framey-syncthing-migration-unit-http-parent-stopped2-2026-10-30.png)
and [restarted bridge](framey-syncthing-migration-unit-browser-restarted3-2026-10-30.png)
captures retain that desktop evidence.

Independent exact-head ownership CI audits passed on
[AMD64](framey-syncthing-migration-unit-ownership-amd-2026-10-30.json) and
[ARM64](framey-syncthing-migration-unit-ownership-arm-2026-10-30.json). Those
separate fixtures verify the upstream runtime and owned service, not signed
Flatpak packaging. The stricter host gates in #493 also accepted the complete
actual local signed-package migration and service reports.

CEF, store receipts and input are synthetic. The installer remains disabled.
No real Steam CEF, managed installation, Frame, wearer-visible content or
physical controller result follows. All four exact-head signed-package CI
jobs, resulting-main CI and every release gate remain required. This evidence
alone does not authorize a merge or release.
