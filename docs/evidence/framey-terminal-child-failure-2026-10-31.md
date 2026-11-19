# Terminal child failure diagnostics and exact-head ARM64 evidence

Verified 2026-10-31T16:19:59.776887+00:00. Tested source `0e8c89a042826957ab5a04f20235ece1bb23e3b7` normally includes
main `3c03e478a2fab181e6bdfe60ada6038663843ab3` while remaining stacked on PR #490. Subsequent evidence-only
changes retain its 168 frozen runtime inputs. No history is rewritten.

## Current pushed-head ARM64 failure

Prior remote head `50a68e4ddd4bcde4571457c6c4d1072fa40686e1` completed 23 of 24 checks successfully;
its ARM64 `terminal-browser` job **failed**. Run 41211232565, job 124566486594,
artifact 13047539726. The downloaded ZIP matches GitHub's published SHA-256
`6ab5f927c500c369aab733a45b2b3f2d0830670c25ebd98407d45262af8a1800`. The checkout log, all 168 input hashes,
reconstructed source archive, bootstrap, pinned loader, official frontend and
complete guest-result packet independently verify.

This failure happens before subscription. The production HTTP requests are
`get_terminals` -> 200/empty list and `create_terminal` -> 200/true. The original
CEF trace records discovery and both list/creation calls succeeding over one
socket, without overflow. There is no later list request, subscription or native
output event. The DOM driver times out waiting for the created terminal's button;
the inspected capture shows an empty Active Terminals section. The browser/HTTP
handlers drain and all recorded owned cleanup completes, including QEMU, browser,
service, original unit, bundle and user manager. Mixed service stop takes
9.805 seconds. Cleanup and
successful backend creation do not qualify terminal UI usability.

About seven seconds of validation plus about 22.5 seconds of method SSH work
approach the iframe's existing 30-second deadline. The artifact does not retain
the child's rejection details or the complete HTTP duration, so a discarded
reply is a hypothesis, not a proved sole cause. This is distinct from the
[earlier subscription timeout](framey-terminal-arm-request-drain-failure-2026-10-31.md).
Both remain failures; no mutation is retried and no deadline is relaxed.

## Diagnostic change and fresh local verification

The owned test driver now records the wait phase, up to 20 child errors of
1,000 characters each, up to 30 button labels of 128 characters, bounded DOM text
and textarea presence on failure. The production HTTP fixture retains those
details in its final failure state and records each method/event HTTP start and
duration. RPC arguments/results are not added to the CEF trace. Only private
fixture diagnostics change; the production parent, panel, method/event scripts,
SSH wrapper, iframe/browser isolation, bootstrap and deadlines remain unchanged.
The main merge preserves the current installer, catalog, Free Loader and Deck
Settings fixtures exactly.

A controlled execution of the actual JavaScript driver simulates successful
creation without a subsequent list button. It preserves the child timeout and
phase, bounds retained errors, emits failure, keeps the existing 60-second DOM
deadline, and performs creation exactly once. All 35 gateway tests pass. The
full server suite passes 1,971 tests in 262.148
seconds, with 16 optional/platform skips. All 18 website tests pass without skips.

An owned networkless AMD64 QEMU replay verifies all 168 frozen hashes,
reconstructed source archive, bootstrap, generated panel, pinned loader/official
frontend and complete guest packet. All 20 production
HTTP requests return 200 (14 methods/6 event polls),
with maximum recorded HTTP duration 6.934 seconds. The original
CEF trace has 17 successful calls over one socket;
4 delivered native events include the private PTY output.
The shell output marker, DOM rows and create/remove lifecycle verify. Handler
draining is empty and no read-only failure diagnostic runs. Mixed service stop
finishes in 7.462 seconds. Every recorded owned
cleanup completes. Three captures were visually inspected; pane overflow remains.

The local successful replay verifies diagnostic integration without reproducing
or repairing the ARM64 failure. The controlled JavaScript case establishes the
new failure snapshot. No globally clean/error-free runtime qualification follows.

## Evidence and remaining gates

[Structured audit](framey-terminal-child-failure-2026-10-31.json) and [raw local/ARM64 reports, packets, logs and
independent verifiers](framey-terminal-child-failure-2026-10-31-raw.json.gz). Raw JSON SHA-256:
`e5b0e05f157df40c31a7689522b9f9cf7469272bd9c418bb41b4aaa869a77597`. Gzip SHA-256: `de0137badc84d5c0cc2dce6efcb7959af043bc203d0c55208f0a4d0d12f72cbf`.

Fresh exact final-head and current-main CI/full e2e/native AMD64+ARM64, ownership,
PC, every triggered package mode and stacked-parent qualification remain gates.
Official Terminal stays partial. Synthetic CEF, receipt and input do not prove
real Steam CEF, an official managed Terminal installation, wearer-visible pixels
or physical controllers. No headset, hourly schedule, user data, tag or release
was touched. Release remains held until every exact release-commit gate and a
separately locked real Frame smoke pass.
