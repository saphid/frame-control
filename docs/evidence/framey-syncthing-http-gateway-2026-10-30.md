# Syncthing production HTTP/panel gateway probe, 30 October 2026

Syncthing 0.2.7 remains blocked from managed installation. The earlier combined
browser replay used a private bridge that called Decky RPC directly. This
optional `--browser-setup --http-gateway` probe adds the production local HTTP
handler, UI-key check, panel receipt/method dispatcher, generated method script,
local SSH wrapper and CDP client to the same disposable signed-package VM.

The probe first runs the existing browser lifecycle. It then starts a separate
owned Chromium page named SharedJSContext. That page implements only Decky's
actual authenticated WebSocket protocol against the published Decky 3.3.0
backend; it is a **fixture CEF page, not Steam CEF or Steam's UI**. Its store
receipt is also an explicit test fixture for this uninstalled candidate. The
probe does not bypass the production HTTP/panel functions, but it does not test
the managed installer or the full production browser parent through that path.

Authenticated HTTP calls must read persisted settings, show Stopped, start the
actual signed Syncthing service, read authenticated REST, reject REST without
its API key, stop and reap the signed processes, and show Stopped again. The
actual service PID and signed process identities join the existing native
report. Missing UI authentication, stale receipts, a different plugin ID, a
modern call to the legacy-only bridge and a missing receipt shim must refuse
before controlling the service. The test logs selected methods/routes/statuses,
never credential values or raw settings.

Production source files and the three catalogue import dependencies are packed
without rewriting them. The guest verifies every file hash before importing
its real HTTP server. The VM still has no network NIC, host home, bus, disk or
session; only the owned guest's loopback is used. Chromium keeps its sandbox.
The HTTP server, Chromium process group and synthetic receipt are cleaned up;
normal migration, sync, ownership-refusal and preserving-uninstall gates remain
required afterward.

## Current evidence

Two networkless container checks confirmed that the real server imports and
that the packed sources include its catalogue dependencies. A UI-only import
failed because frame_catalog imports apk-catalog/build.py; that missing input
was fixed rather than mocking the module. Container import is not runtime or
integration proof.

Two focused guard/packing tests pass: host or wrong-guest refusal precedes
commands/environment changes, and the source bundle includes unchanged
production dispatch, local SSH and catalogue imports. The existing 22 package
input/evidence tests also pass. Full server regression at `f870ceb` passed
1,845 tests in 227.444 seconds, with 16 skips and no failures.
The first combined trial at `88271c9` failed before reaching the HTTP gateway:
the real browser reached the manual-port fallback after one scan returned no
port. The fixture waited only for automatic discovery and timed out. Its 122
source fingerprints match that exact revision; QEMU, Chromium and the private
bridge were reaped. The browser progress report records an active service and
the rendered Port input. The failure screenshot was truncated by the guest
journal and is not credited as visual evidence.

The combined browser probe now enters the known private fixture port through
the rendered input when that supported fallback appears. It records whether
manual entry was needed, and failed captures use bounded chunks. The new trial
also incorporates the pending bounded instance-registry cleanup repair. These
are test-fixture changes; they do not turn a backend scan retry into a UI retry
or claim automatic discovery. The second trial at `49f084f` completed the
browser phase with automatic port discovery (`manualPortFallbackUsed=false`), four Running/Stopped stages,
actual backend RPCs and sandboxed renderer observations. This trial did not
exercise manual entry. Its successful-phase screenshots were not retained
when the later HTTP phase failed, so no inspected visual capture is credited.
All 122 source hashes match that revision.

The HTTP phase reached its process-identity check after service Start returned,
but only the Flatpak launcher existed at that moment. It failed rather than
crediting an unsigned launcher as the runtime. QEMU, both owned browsers, the
HTTP server, bridge and synthetic receipt were cleaned up. The new probe waits
for authenticated REST readiness before requiring signed process identity;
only expected 425/502 readiness responses may retry, and authentication or
unknown HTTP failures still fail. Five focused HTTP tests and 34 package/input/
evidence/cleanup tests pass. The third trial at exact revision
`a8d1187d96bc4c4b58172959a0b85c9fe418b62c` passed the whole probe and an
independent audit of all 122 source fingerprints. The expanded full server regression at `ce5190f`
passed 1,852 tests in 227.550 seconds, with the same 16 skips and no failures.

All four retained captures were independently inspected and show Running →
Stopped → Running → Stopped:

- [Running](framey-syncthing-http-gateway-running1-2026-10-30.png)
- [Stopped](framey-syncthing-http-gateway-stopped2-2026-10-30.png)
- [Restarted](framey-syncthing-http-gateway-restarted3-2026-10-30.png)
- [Stopped again](framey-syncthing-http-gateway-stopped4-2026-10-30.png)

These captures cover the private-bridge browser phase; the subsequent production
HTTP dispatch phase is established by its source-bound request/native report.
This trial used automatic port discovery
(`manualPortFallbackUsed=false`); it does not establish the manual fallback.
The browser lifecycle still uses its private RPC bridge. The separate HTTP
phase exercised the unchanged production dispatch with 105 production source
fingerprints, all five expected refusals, authenticated signed-service REST,
start/stop, and cleanup. Its signed Syncthing process identities matched the
package. All 17 lifecycle checks, 18 ownership refusals, 12 migration checks,
preserving uninstall and owned QEMU cleanup passed. Result SHA-256:
`bed309be4b5824d67b6f1fcccaa5aaed14690c348a2682295dc7641c3ddbc571`.
The JSON companion records the independent audit, all source fingerprints and
capture digests; both
failed development trials remain recorded above and in that companion.

The CI follow-up requests `--browser-setup --http-gateway` in its
AMD64 browser job, binds packed production source hashes to the checked-out
head and keeps the two native package jobs. No CI pass for this new path is
credited yet; ARM64 still runs signed-package checks without this browser/HTTP
probe.

Actual Steam CEF, the production browser parent over HTTP, external SSH
transport, managed install/update/remove, native ARM64 execution of this new
path, real Frame visuals and physical controller use remain unverified. No
real Frame was contacted and the hourly worn schedule is unchanged.


The review branch is refreshed by a normal merge of the exact #479 head
`5a6629155b4b9b9822f6d2c216b47a377b59f2e0`. This changes no production UI or
helper bytes from the passing local HTTP trial. Current-head CI must run before
merge. The later full production browser-parent development trial is separate:
it has not passed and is not enabled by this workflow. In particular, the
browser captures above do not establish that the production parent can complete
its concurrent folder/device reads over HTTP. Installation remains blocked.
