# Notifications: private IPC EOF and clean shutdown

Decky Notifications 1.0.1 remains **partial**. Fresh main
`69c51b251b5fea5d189efa7fb624b13902c62017` failed its AMD64 native runtime gate:
the first plugin stop needed SIGKILL after five seconds, although the loader
parent exited zero. The next start/stop completed cleanly. The strict primary
runtime gate correctly rejected the hidden forced kill.

The failed producer is [job 131046671443](https://github.com/saphid/frame-control/actions/runs/43177953796/job/131046671443),
artifact `13925830546`, ZIP SHA-256
`336449268c02dc4eb8150726c3c0706e76dbd86f008c5c603badff8875481d30`.
Its exact checkout, successful artifact-upload step, ZIP/member digests and
53 committed source fingerprints were independently verified. This failed
artifact remains quarantined outside successful merge evidence.

Only exact archive
`3b22dc337209615f91da566ceb968793dc163b2e509de8535fb5d0fc55817312`
receives the existing child-local IPC EOF adapter, in addition to the existing
private logging repair. It ends only an exhausted peer's connection loop and
keeps the listener available for reconnection. Published unload, connector,
certificate, database, pairing and frontend logic remain unchanged. Missing
helper payload refuses installation; another archive digest receives no repair.
Old managed copies need Update/reinstall. Loader binaries and stop budgets are
unchanged.

Local network/device-isolated published Decky 3.3.0 AMD64 verified:

- Private certificate creation, empty device list, synthetic notification
  read/clear, and fingerprint/database readback after an explicit Unix-peer EOF
  and a loader restart.
- Two parent-only SIGTERM stops in **0.275 and 0.266 seconds**, without forced
  kills or shutdown errors. Original unload messages were present, recorded
  PID/start-time descendants disappeared, and adopted child exits were zero.
- An unrelated sibling and marker survived both stops.
- Removing only the new prefix/helper retained both privacy repairs and
  reproduced a **5.540-second forced kill** after the same explicit EOF. The
  parent still exited zero; this expected negative is not a compatibility pass.
- All 54 tested source fingerprints and console digests matched the local
  sources. The other 115 compatibility rows and all 116 classifications/install
  policies remained unchanged. The other 37 primary probe bodies were unchanged.
- 150 focused store, compatibility, runtime-coverage and IPC tests passed,
  with no skips; the final compatibility wording passed its 31-test suite.
- The owned fake-Frame HTTP installer regression installed/removed all 37 pinned
  fixtures and verified Notifications receipt/API shim lists, partial status and
  exact backend/helper checksums. It passed with zero skips; owned containers,
  network, volumes and image tags were removed. This fixture does not execute
  official plugin backends.

This controlled EOF regression establishes a reproducible failure and repair for
Notifications. The hosted failure lacks a child userspace stack, so it does not
prove what triggered that particular EOF. It does **not** establish the cause
of the older ARM64 whole-service migration shutdown hang. Fresh final-head
hosted AMD64/ARM64 runtime, package and test gates remain required before merge.
Phone pairing, LAN notification delivery, real Frame, exact-release hardware
smoke, wearer/controller use and release qualification remain unverified.

The [audit record](framey-notifications-ipc-eof-2026-11-12.json) and
[compressed raw evidence](framey-notifications-ipc-eof-2026-11-12-raw.json.gz)
retain exact sources, native lifecycle observations, consoles and test output.
