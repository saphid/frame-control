# Notebook child IPC EOF and shutdown qualification

The full native AMD64 job for #707 at `02dc9107` passed Notebook's private
page operations but recorded a 5.23-second first stop and Decky's explicit
`Sending SIGKILL!` warning. Its second stop took 0.214 seconds. A zero parent
exit therefore did not establish clean plugin shutdown. The existing primary
console gate rejected this run. Passing #706 runs on both architectures do
not negate the intermittent failure.

The exact managed Notebook 0.1.5 archive now receives the existing child-only
IPC EOF adapter. The original backend body, frontend, manifest, license and
all other published files remain intact. The adapter changes neither Decky's
parent nor another plugin. Existing installed copies need Update/reinstall;
the compatibility receipt now requires `notebook-ipc-eof`.

A private native AMD64 run using the digest-pinned published Decky 3.3.0 loader
verified default and two synthetic app namespaces, page/selection persistence
across restart, selected deletion with independent file readbacks, and two
RPCs after controlled EOF. Both parent-only stops were clean (0.214 and
0.265 seconds), with no forced plugin kills, shutdown errors or recorded
descendants remaining. The unchanged original backend under the same EOF
control required a forced plugin kill at both stops (5.415 and 5.449 seconds).
These negative controls are expected failures, not compatibility passes.

The [source-bound report](framey-notebook-child-eof-2026-11-14.json) retains
both strict stop observations, console hashes, 61 input fingerprints and the
raw report's SHA-256. The compressed raw report and original hosted failure
are adjacent. The aggregate diagnostic console's `cleanShutdownVerified`
field is not a qualification assertion; the explicit Notebook stop records
and primary console gate are authoritative. The local store suite (122),
Notebook transaction tests (4), runtime coverage (3), compatibility tests (34)
and shared IPC tests (4) pass.

Independent read-only audits retained alongside this report confirm #707's
exact-source original failure, both architectures of its repaired sample,
and #706's exact-source sample/native/Terminal artifacts. These are distinct
historical inputs, not evidence that this new Notebook repair passed ARM64.
Fresh full hosted qualification and ARM64 repair checks remain pending.

Frame SSH timed out again. No headset was modified, no wearer was confirmed,
and no hardware or worn-VR result is claimed. The controlled EOF reproduces a
failure mode; it does not establish the original ARM64 shutdown trigger.
Version v0.4.63 remains an unpublished draft and its tag must be preserved.
