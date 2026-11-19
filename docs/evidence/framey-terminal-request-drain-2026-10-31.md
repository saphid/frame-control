# Terminal failure diagnostics and in-flight requests — 2026-10-31

Hosted source `f032af38e795aa5471b3a576c74cdc12a640be86` fails the
[ARM64 production browser job](https://github.com/saphid/frame-control/actions/runs/41200897155/job/124536323560).
The artifact ZIP matches GitHub SHA-256
`247f8388296b08b77db9b435822c49e69eef7c1b0acf8ae4ba94699c2f64ab2a`.
All 168 source fingerprints, the reconstructed source archive, bootstrap,
published Terminal archive and frontend digest match the exact head. The complete
checksummed guest packet decodes to the retained result without truncation.

Seven production method calls return HTTP 200. The following
`subscribe_terminal` and event poll return HTTP 503 after SSH timeouts of
25.112 and 25.140 seconds. `send_terminal_buffer` never runs; the terminal pane
has no output. Panel-ready and running-backend status do not prove usability.
This run has no method failure diagnostic, so its subscription failure remains
unexplained. The two-vCPU ARM64 guest uses QEMU TCG; it is not a direct native
ARM64 latency measurement.

The fixture read its failure trace before closing the parent and stopping HTTP.
A request still running at that point could fail later and miss the diagnostic
trigger. Source `2a8a941e` closes the owned parent, stops accepting HTTP, and
waits up to 35 seconds for existing handlers before deciding which read-only
diagnostic to run. The separate CEF facade stays alive during diagnosis. An
incomplete drain suppresses diagnostics and cannot pass the fixture. No failed
method is retried, and production code, SSH deadlines and acceptance criteria
are unchanged. This repairs missing evidence, not the ARM64 subscription failure.

## Verification

Twelve focused tests pass. A real owned loopback HTTP request reproduces the
late-failure ordering and verifies its failure is retained before diagnosis.
Another test verifies the drain returns with a pending handler rather than
waiting without a bound, and releases ownership through exceptions. Existing
read-only diagnostics, redaction, process reaping, terminal state and both guest
source manifests pass. The full suite passes 1,963 tests in 267.547 seconds,
with 16 optional/platform skips; all 18 website tests also pass.
The isolated AMD64 VM replay at the frozen repair source also passes:
all 168 fingerprints match, all 20 production HTTP requests return 200
(14 methods and six event polls), and four backend events deliver real private
PTY output to the terminal rows. The parent closes, HTTP stops and the drain
reports zero pending handlers before diagnostics. No failure-only diagnostic
runs. The owned Decky service stops with exit zero in 2.818 seconds; the private
shell, browser, HTTP server, unit, bundle, user manager and QEMU are cleaned.
Browser sandboxing remains enabled. Three capture payloads are hashed; these
new captures were not visually inspected. Synthetic CEF, receipt and input
remain explicit. Fresh exact-head ARM64 replay is still required.

The failed hosted run stops the owned Decky service with exit zero, restores
its dummy unit, removes its private bundle, stops its user manager, and reaps
QEMU. Decky console cleanup errors remain; no global clean-console claim is
made. No real Frame, wearer, controller or hourly schedule was accessed.
Terminal compatibility stays partial. This evidence qualifies no release.

[Structured provenance and request audit](framey-terminal-request-drain-2026-10-31.json).
[Raw local result and verification logs](framey-terminal-request-drain-2026-10-31-raw.json.gz).
The raw local result retains the probe's bounded runtime console; no independent
complete-console audit or global error-free shutdown claim was added.
