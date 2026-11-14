# Native ARM64 browser readiness remains blocked

Exact PR head `ce69eaf1eb383a25ddb8e1a5eb502249b388e7fc`, run 41084788607, job 124162979768 failed before the first browser stage. Artifact 12993527868 and both committed source inventories were independently checked. The paired JSON retains their counts, archive digest and bounded readiness trace.

Eight initial connection attempts failed, then eight retained attempts connected but did not observe the panel ready. The trace overflowed after sixteen entries. The final CDP target read timed out. No browser RPC calls, stages or captures were verified. The exact root cause remains unknown; a live Chromium process does not establish a working frontend.

The fixture previously ignored the shipped iframe's `framey:error` messages. The follow-up retains up to sixteen messages of at most 1,000 characters, only from the owned iframe, plus the last readiness attempt after the bounded trace fills. A Node regression exercises that actual parent script with foreign-source rejection, capacity/length limits and an unchanged false readiness state. This improves evidence; it does not establish a runtime fix. No deadline, sandbox or passing gate is relaxed.

Owned Chromium, HTTP bridge and QEMU cleanup succeeded. The installer remains disabled. Steam CEF, ARM64 browser usability, physical controls and wearer visibility remain unverified. No real Frame was contacted.

The diagnostic follow-up passed the full local regression: 1,864 tests, zero failures and 16 skips in 222.781 seconds. The paired JSON binds that log and the exact-prior-parent red reproduction.
