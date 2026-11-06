# MusicControl child IPC EOF and shutdown

Exact #566 head `368b70e96324f558883f26ad2f58b04c8fbf392e` failed
[native ARM64 job 127741537599](https://github.com/saphid/frame-control/actions/runs/42171935925/job/127741537599)
in MusicControl 1.1.6, primary case 12. Its private media RPCs passed, but
Decky killed the child after its five-second stop deadline. The loader parent
returned zero. This is a failed runtime gate. Artifact `13481403474` is
retained separately from successful qualification artifacts; its uploaded
archive digest, exact checkout, pinned loader and all 47 source fingerprints
were independently checked. That older probe did not fingerprint the managed
backend body. The [JSON record](framey-music-control-ipc-2026-11-06.json)
binds the failed report and the new local observations.

MusicControl store entries 12 (1.1.6) and 111 (1.1.7) share the legacy child
transport. Closing its Unix IPC peer reproduces an event-loop spin: later
RPCs time out and Decky requires a forced stop. Deliver the existing
`framey_decky_ipc.py` EOF adapter only to these two exact published archive
digests. It ends the closed connection's loop while retaining later
connections. Decky's parent, other plugin processes and authentication are
unchanged. The original legacy class calling convention and system D-Bus
library-path repair remain. These published backends have no `_unload`
method; the probe requires Decky's actual legacy unload path and zero-exit
child cleanup, rather than an API1 goodbye message.

Local native AMD64 used the digest-pinned published Decky 3.3.0 binary in
network/device/session-isolated disposable containers. Both entries passed
silent private MPRIS discovery, metadata, transport, seek and volume checks,
then read-only RPCs after an explicit peer EOF. Each passed two parent-only
stops at 0.214/0.225 seconds, with zero forced kills, zero-exit adopted
children and no remaining recorded descendants. Restart discovery and RPC
readback passed; exact private player state and an unrelated sleeper survived.
The fixture cleaned its own processes. Both previous-managed-code controls
remove only the EOF adapter, keep the existing D-Bus environment repair and
verify the restored backend hash. They reproduced the expected forced stop
at 5.226 seconds (12) and 5.224 seconds (111). They are negative controls,
not compatibility passes. The independent audit verified all 49 runtime
source fingerprints, backend/helper hashes and console digests. The existing
bad-bound-method negative for 111 also still fails legacy dispatch as expected.

The relevant local suite passed 127 tests without skips. It covers receipt
requirements, legacy media methods, exact helper delivery, unknown-archive
non-adaptation and byte preservation when an update lacks the required
helper. Compilation and whitespace checks passed. Fake-Frame e2e assertions
now require both receipt markers and the delivered helper digest; fresh
hosted e2e and native AMD64/ARM64 qualification remain pending.

Both compatibility entries stay partial. Existing managed copies need an
explicit update or reinstall; their old receipts now say so. No new browser,
real Frame playback, wearer-visible UI or controller test was performed.
No real headset was contacted. This MusicControl repair does not establish
the cause of, or a fix for, the separate retained ARM64 Syncthing migration
shutdown timeout. #566 and release qualification remain held until their
exact-commit gates pass; the historical migration investigation and all
release/installer/checksum/publisher/locked-Frame gates remain outstanding.
