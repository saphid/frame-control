# Terminal failure-only fatal diagnostics

The retained ARM64 browser failure at `37aa39f9579aac242aae03c726e533549a6f2a29`
([run 41147963665](https://github.com/saphid/frame-control/actions/runs/41147963665))
passed its first five real method requests, then timed out on unsubscribe and
get-terminal requests. Its separate read-only diagnostic exited with SIGSEGV.
Neither that exit nor the sampled import frames prove the production failure's
cause. The failed capture and previous audits remain unchanged.

The diagnostic wrapper requested periodic tracebacks but did not enable the
fatal-signal handler. A controlled owned child now demonstrates the difference:
before, SIGSEGV produced no sampled frames; after, it produces the whitelisted
`Segmentation fault` reason and basename/line/function frames. Raw stderr,
addresses, source lines and private values remain excluded. The child disables
its own core dump for this test and is reaped. The two new tests first failed
against the original diagnostic; all seven diagnostic tests now pass, together
with two Terminal-state tests and three runtime-coverage tests.

The branch normally merged main `358e423a62300689543e2083d5213af763c03a46`.
The overlapping Terminal and Bluetooth fixture bodies were preserved by AST
comparison. At frozen source `d53c1ac5e8871282a5106b2815f6ad9536381f72`, an owned,
networkless AMD64 QEMU VM passed the actual production HTTP parent, method/event
flow, private PTY input/output, resize, remove/reload and configuration checks.
Its 20 requests succeeded; four real backend events delivered the private
output. All 166 source fingerprints, bootstrap and complete guest-result packet
were independently verified. The Decky service stopped with exit zero in 2.89
seconds; the owned QEMU was reaped. The [audit](framey-terminal-fatal-diagnostic-2026-10-31.json)
records these bounds. The terminal/output/removed captures were inspected; the
output capture shows the private command result and the final capture an empty
terminal list. Complete raw Decky loader logs are absent, so no error-free
loader-console claim follows.

The successful VM replay did not invoke a failure diagnostic. It used synthetic
CEF, a synthetic receipt and synthetic input, with the test-only Terminal
candidate. The production request and deadline sources are byte-identical to
the previous failed head. All 116 compatibility records match current main;
no production Terminal adaptation or compatibility promotion is enabled.

This change adds evidence collection only after a failed real request. It does
not retry or replace that request, warm its imports, change its deadline or
turn it into a pass. Fresh instrumented ARM64 CI remains required. Real Steam,
managed Frame installation, wearer-visible UI and physical controllers remain
unverified; no headset or hourly schedule was touched.
