# Terminal RPC trace before failure diagnostics, 31 October 2026

The ARM64 subscription failure recorded at remote PR #492 head
`f9094fa6a2bb40609fa44d862aa8247549126538` did not retain the original CEF
request trace. Its SSH timeout alone cannot establish whether a call reached
Decky. Local source `b591ce52b16baff8b37494d22221e8ba43b89f91` records that
bounded trace after handler draining and before any modified read-only failure
diagnostic, on success and failure. Terminal method labels are allowlisted;
unknown method labels remain `other`. RPC records omit arguments and results.
Existing synthetic native-event evidence still includes private fixture output.
No production code, bootstrap, isolation, deadline or acceptance gate changed.

The actual fixture JavaScript has a controlled unanswered subscription test.
It verifies the sent method, pending-to-timeout transition, one shared socket,
allowlisted labels and omitted private RPC arguments/results. A pre-Decky SSH
startup timeout would instead leave no subscription record. All 34 gateway
tests pass. The full server suite passes 1,964 tests in 259.733 seconds with
16 optional/platform skips; all 18 website tests pass without skips.

An isolated networkless AMD64 QEMU replay uses published Decky 3.3.0 and the
private Terminal dependency/lifecycle candidate. All 168 frozen source hashes,
the reconstructed source archive, bootstrap, loader, official frontend and
complete encoded guest packet are independently checked. Only
`tests/decky-runtime/terminal_http.py` differs among those inputs from the
prior remote head. The additional unit test is outside that runtime inventory.

All 20 production HTTP requests return 200: 14 plugin methods and six event
polls. The trace records 17 successful CEF requests over one socket, including
discovery and direct fixture queries. Subscription, buffer retrieval, input,
unsubscription and removal are labeled. Five delivered events include the
private PTY output marker; terminal rows and the private marker-file digest
verify the round trip. The trace is not overflowed, is marked pre-diagnostic,
and follows a successful drain with zero pending handlers. No failure-only
diagnostic runs.

The mixed Decky service reaches inactive/MainPID zero/exit zero in 7.959
seconds. Shell, browser/target, HTTP server, SSH observer, unit/receipt, bundle,
user manager and QEMU cleanup checks pass. The three hashed captures were
visually inspected: the initial terminal route renders, the output capture
shows the command and `framey-browser-output`, and the removal capture shows
the empty terminal list. The panel still overflows horizontally; this change
does not address its layout.

The earlier ARM64 failure remains a failure and its cause remains unproved.
This local AMD64 pass qualifies trace retention, not an ARM64 repair or a
globally clean runtime. Synthetic CEF, managed receipt and input do not prove
real Steam CEF, an official managed Terminal install, wearer-visible pixels or
physical controller usability. Fresh exact pushed-head/current-main CI, e2e,
native, ownership, PC and package gates remain necessary. No headset, hourly
schedule, tag or release was accessed or changed.

[Structured audit](framey-terminal-cef-trace-2026-10-31.json) and
[raw report, packet, logs and verifier](framey-terminal-cef-trace-2026-10-31-raw.json.gz).
