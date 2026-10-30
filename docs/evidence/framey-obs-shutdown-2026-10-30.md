# OBS relay signal shutdown regression, 30 October 2026

Main `f78a4ab2dfff84d3215bcf9e9124a6a45a7f11b4` failed Ubuntu server tests
in [job 123932818070](https://github.com/saphid/frame-control/actions/runs/41016148971/job/123932818070).
The signal-mode relay test timed out after eight seconds; killing the relay
alone also left the fake SSH child's inherited output pipe open.

A local stand-in SSH probe reproduced the blocked relay after 139 attempts.
Its thread dump showed the main thread blocked in `relay()`'s stream read and
the watchdog waiting. A handler that merely sets a Python flag still reproduced
it: Python executes handlers on its main thread, so a signal delivered to the
watchdog thread need not interrupt the main thread's read.

The regression now explicitly sends SIGTERM to the watchdog thread with
`pthread_kill` after the first real UDP packet. The previous implementation
fails this deterministic case with the same eight-second timeout. The test
uses an owned process group and cleans the relay and fake SSH child on failure.
No real SSH host, headset, mirror or wearer was contacted.

The helper now uses Python's low-level signal wakeup descriptor. A nonblocking
POSIX pipe (Windows socket pair) carries the signal byte to the watchdog,
which terminates and reaps SSH to unblock the stream read. The Python handler
returns normally; requested termination is a clean exit. Cleanup stops the
child before closing its output pipe, then restores the prior handler and
wakeup descriptor. The desktop control-pipe path and startup/stall watchdogs
remain covered.

Thirteen OBS tests pass locally, including the targeted worker-thread signal,
ordinary SIGTERM, control-pipe closure, stubborn child, startup/stall, packet
boundaries and mocked Windows sender behavior. A further 200 consecutive
ordinary subprocess signal shutdowns completed without a timeout. The full
suite and cross-platform CI remain required before merge; native Windows
wakeup handling and real OBS/headset streaming are not established by the
Linux and mocked tests.
