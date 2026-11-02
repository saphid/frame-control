# Discord Status IPC lifecycle, 2026-11-01

Exact official store ID 37, Discord Status 1.5.0, ZIP SHA-256
`00a45dd919abb6e050685e1e408ce8023b9c4a09d6e91ba528d50aed2a63bf45`.
This is partial compatibility. No real Discord account or Frame was contacted.

The published backend does not initialize `pipe`, replaces an active pipe
without a protocol CLOSE, leaves a failed handshake pipe assigned, closes a
socket only after a successful CLOSE send, and calls async disconnect from
unload without awaiting it. Replacement does not establish a persistent file
descriptor leak: CPython can close the old socket through garbage collection.

Only this exact archive receives the existing Decky child-IPC EOF helper and
a small pipe lifecycle adapter. Original backend bytes remain between a
prefix and postlude; all other original archive files are unchanged, including
frontend and license. No root flag, policy or frontend change is made. Unknown
digests receive no adaptation; missing helper payloads refuse installation.
Existing managed installations need update or reinstall to receive the fix.

Focused POSIX tests verify replacement, fresh/repeated cleanup, clear,
rejected-handshake/retry, broken-peer close, original archive preservation,
changed-digest exclusion and missing-payload refusal. Five unchanged-original
regressions produced two failures and two errors before the adapter; the
initial test-fixture setup failure is retained separately, not counted as the
regression. Windows skips only these POSIX transaction/Unix socket tests.

Published, digest-verified Decky 3.3.0 AMD64 ran in a disposable non-root,
networkless, device/session-isolated container. Actual discovery and 14 RPCs
reached the managed original backend. A disposable AF_UNIX peer retained raw
framing for six connections and 18 frames: default/custom application IDs,
original activity fields and PID/nonce, replacement, empty clear, rejected
handshake/retry, explicit disconnect and unload at active connections.
Every connection received CLOSE before client EOF, before fixture cleanup.

Two strict parent-only stops completed in 0.236 and 0.214 seconds, one after
controlled child-IPC EOF; loader and adopted-child exits succeeded, exact
recorded descendants disappeared, no forced kills or shutdown errors occurred,
and an unrelated sibling survived. Restart rediscovered the same plugin.
An independent audit decoded every wire frame and checked source hashes,
payloads, process ownership, stops and console hashes. Its first attempt
incorrectly required every descendant to be reaped by the probe; Decky reaps
some itself. That audit-only assumption was corrected without rerunning the
native test. The generic console `cleanShutdownVerified` flag remains false
because the generic recorder never certifies plugin shutdown; the explicit
two-stop records supply the strict shutdown evidence.

Full local server suite: **1,976 tests, 15 platform/optional skips**. Website:
**18 tests, zero skips**. Full disposable fake-Frame suite: **53 tests, zero
skips**, all 116 exact catalog records, **69 install/remove and 47 refusal
outcomes**. Source hashes retain the native inputs and all other 115 catalog
rows. Owned simulator containers, volumes, networks and image tags were
removed; independent cleanup inspection passed and the shared simulator stayed
healthy. The catalog suite does not execute every official backend. See the
[summary](framey-discord-ipc-lifecycle-2026-11-01.json) and
[raw logs, native wire/console evidence and audit programs](framey-discord-ipc-lifecycle-2026-11-01-raw.json.gz). Hosted ARM64 runtime and exact-publication CI remain
required. Actual Discord presence/account, Steam event/shortcut detection,
artwork fetch, connected browser UI, real Frame and worn/controller behavior
remain unverified. The original blocking receive/framing and hard-coded
Flatpak user path assumptions remain outside this lifecycle fix.

The full suite ran before the test-only `ExitStack` portability correction; all
eight focused lifecycle tests then passed on Python 3.9 and Python 3.12. After
normal integration of main `149b6ce3995a6ca98106eef32085257e56d9dd58`, the
three added timeout diagnostic tests and three runtime inventory tests pass
separately. All 28 native input hashes remain unchanged. The final metadata-only addition
of two required-shim names makes old installed copies show the existing
Update/reinstall warning; compatibility stays partial. Both Python versions
pass the eight focused tests again, including that receipt-based warning, and
the compatibility suite passes. All 116 catalog versions/digests/flags/policies
and e2e execution code are unchanged. The full server/catalog/native producers
were not rerun for this metadata change; their results remain attributed to
the original source, with fresh hosted final-head CI still required.
