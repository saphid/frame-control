# Terminal ARM64 request-drain failure, 31 October 2026

PR #492 exact head `f9094fa6a2bb40609fa44d862aa8247549126538` fails
[ARM64 job 124552480830](https://github.com/saphid/frame-control/actions/runs/41206484346/job/124552480830).
Artifact 13044907459 has independently verified ZIP SHA-256
`1ee91e8d9affa0c8b868dbee1f263b51625275b57f3375c259f04197a5dfc722`.
The exact failed job/checkout, all 168 source fingerprints, bootstrap and
complete encoded guest packet are checked. This record was captured as local
follow-up evidence and committed later; it is not part of the audited head.

The new diagnostic drain succeeds with zero pending handlers. The production
status request returns HTTP 200 in 12.434 seconds. The actual frontend reaches
its terminal route and the trace retains ten plugin/event requests. Nine return
HTTP 200; `subscribe_terminal` returns HTTP 503 after its unchanged 25-second
SSH deadline (25.098 seconds observed). `send_terminal_buffer` is never called;
there is no command/output/close/reopen round trip. Two event polls return empty
results. The inspected failure screenshot shows a blank terminal output area.

The failed method's three process samples show its Python child runnable with
CPU ticks 69/284/463; SSH/shell ancestors wait for children. A later modified,
read-only `get_terminals` diagnostic exits zero in 7.398 seconds with one
terminal. It reports frame_steam cumulative imports of 5.238 seconds and a
sample in http.client/socket imports. These are post-failure diagnostic data,
not a passing replay or proof of the sole cause. No timeout, production method,
event or UI code was changed in response to this run. No blind rerun was made.

The owned QEMU and user manager are reaped, HTTP handlers drained, browser/target
closed, SSH observer removed, synthetic unit restored and owned bundle removed.
The service reaches inactive with MainPID zero/exit zero. Retained console still
contains PTY EIO and loader shutdown CancelledError; no global clean-runtime or
release qualification follows. Other jobs in the workflow remain live.

The fixture uses a networkless owned VM, published Decky 3.3.0, private Terminal
dependency/lifecycle candidate, synthetic CEF facade and managed receipt.
Production adaptation remains disabled and compatibility remains partial.
No real Steam CEF, managed real Frame, physical controller, wearer-visible,
tagged installer or release proof was obtained. The headset and hourly schedule
were untouched. Next: investigate bounded method startup under concurrent parent
polling while retaining the failed exact replay and unchanged production deadline.

[Structured audit](framey-terminal-arm-request-drain-failure-2026-10-31.json) and [raw packet/logs/verifier](framey-terminal-arm-request-drain-failure-2026-10-31-raw.json.gz).
