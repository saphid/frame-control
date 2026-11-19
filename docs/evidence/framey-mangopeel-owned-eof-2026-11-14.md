# MangoPeel controlled EOF and recorded cleanup, 14 November 2026

The native-only follow-up strengthens #509's earlier launcher-exit proof.
Product UI/installer bytes and all 45 primary cases match `04a4cdb4`; the prior
three fake-Frame tests still cover identical product code. All 160 focused
store, compatibility, coverage and IPC tests pass.

The repaired backend passes private profile writes, real inotify changes and
queued reload, then accepts an RPC after a controlled child IPC peer closes.
Only the loader parent receives SIGTERM. The stop records every observed
owned descendant's PID/start identity, reaps recorded adopted children and
requires no recorded survivors, no forced plugin kill, zero adopted exit
statuses, a complete shutdown console and a stop below five seconds. The
unrelated private process and configuration survive.

A separate control removes only the child-IPC prelude/helper while retaining
the same managed watch-thread repair. It reaches the controlled EOF without
performing the positive's preliminary reload. It reproduces one five-second
forced plugin kill and is explicitly not a compatibility pass. Its recorded
identities are cleaned up, but its forced kill is retained as a failure mode.
Every source binding and complete console digest is independently checked.

The first control run completed its stop but failed report construction by
trying to hash the intentionally removed helper. The complete failed log and
partial report remain in the compressed evidence. Reporting None for the
absent control helper repairs that fixture error; the full positive/control
rerun passes. No production changes were needed.

Fresh exact-head full hosted/native ARM64 and package/e2e gates remain required.
This controlled trigger does not establish the sole cause of historical ARM64
shutdown failures. Actual overlay, Steam/Frame, integrated browser, physical
input and worn VR remain unverified.
