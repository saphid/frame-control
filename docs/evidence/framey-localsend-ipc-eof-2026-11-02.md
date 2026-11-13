# LocalSend child IPC EOF repair — 2026-11-02

The strict ARM64 primary gate on #551 head `133b5d055f2f3638294b714e6307013c23a56061` failed case **125 / Decky Localsend 0.4.5**. Decky forcibly killed its child after five seconds without completing the original unload callback. Failed job **125113332819**, artifact **13118962640**, SHA-256 `7eef42262a1b289c22fac46860a0ae2911adb7f8ba9bc69742eedeff886f0edb`, is retained; all 41 source fingerprints bind the failing publication. No rerun replaces the failure. Download All's primary target passed earlier in that run, but its negative was not reached and the failed run does not qualify #551.

A separate native AMD64 RED on `49b1b559d740ab38fb8d3d32afe203f4338e4db6` reproduces a post-EOF RPC timeout, forced cleanup and no unload callback. The same committed LocalSend probe is used for RED and GREEN, bound by all 42 source hashes.

Implementation `108b83384bb9b2e73b1aafae6ff88201d928dad0` is based on #551 `133b5d055f2f3638294b714e6307013c23a56061`. It prepends the existing child-only IPC EOF adapter to exact cached **store 125 / Decky Localsend 0.4.5**, ZIP `e271ccb55eb23f918b99a69f79aec905df4c9b2ef7b23bbf4ec1c2d1a6f0c6b7`. Original backend SHA-256: `db03f9201fe50b75dea99a7a05b54ec3f352d1bdfe174115b0e569154198d8ad`. The helper remains unchanged: original x86 SHA-256 `d448d03861d578685e6c70ea3ace25eb34fca99cb9d4f98bf51ba23aa5cae843`; existing ARM64 SHA-256 `e20363237e606ee65eae857792176d21a0bb8ba863489952728eaf2b13277dae`. Adapter delivery is atomic and recorded as `localsend-ipc-eof` alongside `localsend-digest-native`.

## Verification

The first full e2e run on `2ea49aae358eb5d561dfbcd4c3484813bb4e535a` retained one failure: a second LocalSend receipt assertion still expected only the old shim. Commit `108b83384bb9b2e73b1aafae6ff88201d928dad0` corrects only that assertion. Its failed log and cleanup record are retained; no failed CI run was rerun. The already-passed unit suite and native probe ran on `2ea49aae358eb5d561dfbcd4c3484813bb4e535a`; all unit discovery/production inputs and all 42 native fingerprints are unchanged on `108b83384bb9b2e73b1aafae6ff88201d928dad0`. Full corrected e2e runs on `108b83384bb9b2e73b1aafae6ff88201d928dad0`.

- **2044 full unit tests**, 15 platform/optional skips, 282.723s. Warnings remain in raw logs; optional skips do not qualify release gates. Missing adapter prevents installation. Original archive members other than managed main/helper are preserved.
- Published Decky **3.3.0 native AMD64**: five status/configuration/stopped-proxy RPCs, including status after actual child-peer EOF and restart. Two parent-only SIGTERM stops complete in **0.215s / 0.315s** with original unload callback, notification-server stop, removal of `/tmp/localsend-notify.sock`, zero adopted-child exits, no forced kill and no exact owned descendants left. An unrelated sibling and private marker survive. Network helper remains stopped.
- Explicit negative strips only the IPC prefix/module from the disposable managed install. Actual peer EOF produces the original forced child kill in **5.225s**, missing callback and retained notification socket. That force is not counted as normal shutdown.
- Complete disposable fake-Frame e2e: **53 tests / zero skips**, 415.888s; **116 pins / 69 install-removes / 47 refusals**, zero unclosed HTTP socket warnings. Official backends are stubbed. Owned Compose resources are gone, prior image tags restored, shared simulator identity/start/restart/healthy state preserved.
- Installer/APPLY, checker, e2e and store tests outside LocalSend match parent by AST. Existing helper delivery/digest/ELF checks remain. All 40 native case values/order remain except added case125 shim; all 116 pins/policies/ratings and other 115 complete catalog rows, shared adapter and strict producer gate remain unchanged. Generated docs/diff checks pass.

## Limits and integration

Compatibility stays partial; installed copies require Update/reinstall. Fresh exact-publication hosted CI, full **40 primary + 22 negative native cases / 42 source inputs** on AMD64 and ARM64, e2e, both ownership/service artifacts and all four package modes remain required. Integrate this child into #551 only after qualification, then require fresh exact merged-head qualification for #551 before main. #545 and release remain held.

No fresh ARM64 repair proof, helper start, network discovery/transfer, browser replay, actual managed Frame service, real Steam CEF, Frame pixels or physical controller proof is added. Scoped owned cleanup does not certify a globally clean host. No real headset, schedule, security setting or pre-existing user data changed.

[Bound summary](framey-localsend-ipc-eof-2026-11-02.json) · [Raw failures, observations and auditors](framey-localsend-ipc-eof-2026-11-02-raw.json.gz).
