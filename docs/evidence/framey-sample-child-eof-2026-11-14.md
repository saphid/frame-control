# Sample child IPC EOF, 14 November 2026

The original ARM64 sample-runtime artifact from PR #706 records two clean stops and a forced child SIGKILL at the third stop. Its 19 source bindings and console digest were independently checked and the failure is retained separately. All three settings snapshots had persisted with mode 0600. The original trigger remains unproven.

A controlled peer EOF against the unchanged main sample reproduces the forced kill on native AMD64. The red fixture and its 19 input fingerprints are retained. The fix bundles the existing managed child EOF helper and installs it from the sample's Decky `_main` hook. It changes only this sample child socket's EOF handling.

Source commit `60001bb62c8b0916d966cf945fe24364199d13c8` passes the strengthened native probe: three controlled EOFs, three successful post-EOF settings RPCs, three parent-only clean stops, no remaining recorded descendants and unchanged restart/preservation checks. All 21 input fingerprints match the commit. The 26 sample/packaging/bridge tests pass. The companion JSON and compressed reports retain the exact stop durations, digests, snapshots, transcripts, red fixture and setup failures.

Two default-network builds were stopped with exit 143. The unchanged Containerfile succeeded with a host-network prebuild, after which the original runner reused its cache. Plugin execution stayed networkless. The temporary base image is removed after qualification.

Fresh hosted ARM64/native, sample browser and general CI are still required. This is a controlled EOF reproduction and repair; it does not establish the original ARM64 trigger, the historical Terminal shutdown cause, real Frame behavior or worn/controller/scrolling/VR-keyboard usability.
