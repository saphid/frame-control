# ARM64 Syncthing browser gate: failed readiness

PR #483 at `1883860edecd611eb382f82ccc435cac5e1ab010` failed its native ARM64 browser/HTTP job in [run 41071714150](https://github.com/saphid/frame-control/actions/runs/41071714150/job/124117252227). This is a failed gate, not a runtime compatibility pass.

The independently audited artifact `12988086652` has SHA-256 `3946c5ca13b05b41a177a24fa5eb870ec172f6f84ef222117d1d811ddca9c447`. All 123 exact-head source fingerprints and 122 input fingerprints matched. The report retained the original ARM64 install/user/unit/host budgets of 900/2400/2460/2520 seconds.

The browser failed with `Browser CDP/panel readiness unavailable`; the last readiness error said the expected owned fixture page was unavailable. It reached zero browser stages and zero browser RPCs, with no captures. The old report did not retain browser stderr, so it does not establish the cause. The package and service assertions in the report do not satisfy the browser gate. Owned browser, bridge and QEMU cleanup were verified.

The follow-up records bounded diagnostics from the disposable owned browser after failure: process state, port-file presence, the final 2048 stderr bytes, and a bounded CDP target summary without raw target URLs. It preserves the original exception and leaves readiness deadlines, sandbox and success requirements unchanged. A fresh exact-head native ARM64 browser run and independent artifact/capture audit are still required.

Syncthing installation remains blocked. Full production-browser-parent, actual Steam CEF, real Frame visibility and controller usability remain unverified. No headset was contacted.

See [the machine-readable audit](framey-syncthing-arm-browser-failure-2026-10-30.json).
