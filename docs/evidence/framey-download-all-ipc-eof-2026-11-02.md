# Download All child IPC EOF repair — 2026-11-02

The strict ARM64 primary gate on #545 head `4e032cfb` failed case **131 / Download
All 1.1.0** after AlarMe passed. Decky forcibly killed its child after five
seconds, without running the published unload callback. Failed artifact
**13118620763**, SHA-256
`6ee979011c23a9c163b1fc4b4379c74232d88f5d5eb1201d93f302db321611d4`, is retained;
its checkout and all 41 source fingerprints bind the exact failing publication.
No rerun replaces that failure. A separate AMD64 red probe on `ea8abf79e0bb08adc02b075ccedef7306a972edf`
reproduces a post-EOF RPC timeout followed by forced cleanup and no unload.

Implementation `1c39336f60726ca16e014904bbc9a0086dbce52e`, based on main `84f5efd3fbde8525b473f11c3bd2071d7ffb3e82`, prepends the existing child-only
EOF adapter to exact cached store **131 / Download All 1.1.0**, ZIP
`0641231eec139e3231e7b5369d0dbacefd686b52e3f2fffb39384876881408da`.
The original backend SHA-256 is
`a205e2537490f156f9162277c58d873da096693823a1cc2d25f870592a735e17`.
The existing queue frontend transformation is unchanged. All 40 native cases,
116 pins/policies/ratings and the other 115 complete catalog rows remain.
Whole installer/APPLY, checker, e2e and store-test ASTs outside Download All
match main. The shared adapter and strict producer gate are unchanged.

## Verification

- **2043 full unit tests**, 15 platform/optional skips,
  281.777s. Unit ResourceWarnings are retained; skips do not qualify
  native or release gates. Store transactions verify missing-adapter rollback,
  unchanged other archives, receipt coverage, preserved original members and
  the original frontend queue fixture.
- Published Decky **3.3.0 native AMD64**: three logging RPCs, including after a
  real child-peer EOF and after restart; two parent-only stops in
  **0.214s / 0.265s**. Original unload callbacks, zero adopted-child
  exits and removal of exact owned identities are observed. An unrelated
  sibling and marker remain. All 41 source hashes and reconstructed backend /
  adapter bytes bind the implementation. The **same native probe** retains
  the original red and repaired green behavior.
- Separate explicit negative removes only the adapter prefix/module from the
  disposable managed backend. A real peer EOF requires the old forced child
  kill in **5.234s** with no unload callback. Its force is not a successful
  normal shutdown. The default primary gate continues to reject forced kills.
- Complete fake-Frame e2e: **53 tests / zero skips**, 416.518s,
  **116 pins / 69 install-removes / 47 refusals**, zero unclosed HTTP socket
  warnings. Official backends are stubbed. Owned Compose resources are gone,
  prior image tags restored and shared simulator state preserved.

## Limits

Fresh exact-publication hosted CI, full native AMD64/ARM64 cases, e2e,
strict ownership/service and all four signed-package modes remain required.
No current ARM64 repair proof, real Steam queue/callback, new browser replay,
real Steam CEF, Frame or physical controller proof is added. Catalog rating
stays partial; installed copies require Update/reinstall. Scoped cleanup
checks do not certify a globally clean host. No real headset, schedule,
security setting or pre-existing data change. #545 and release remain held.

[Bound summary](framey-download-all-ipc-eof-2026-11-02.json) · [Raw failures, observations and auditors](framey-download-all-ipc-eof-2026-11-02-raw.json.gz).
