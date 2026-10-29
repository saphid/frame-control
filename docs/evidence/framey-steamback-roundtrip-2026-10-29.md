# Steamback private save round trip, 29 October 2026

The exact official Steamback 1.0.0-1 archive for store ID 46 has SHA-256
`ed5f2fbb47cdfc3aa9a4349a139ab20c29976117a3be0de7e8a588bb265ee7f3`.
The managed archive and empty native RPC baseline are documented in
[the preceding evidence](framey-steamback-native-2026-10-29.md).

`python3 scripts/framey-test-decky-runtime.py --case 46 --output REPORT.json`
passed locally on native x86_64 with the published Decky 3.3.0 loader,
SHA-256 `e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181`.
The local report has SHA-256
`e3e3b0c29fceefe9557bd7370ae35cbe2222514d0dd676ab0776a7d555c09e49`.

The runner gives Decky a private home, no network, no devices, no host session
and no real Steam files. Inside it, a single private account, app manifest,
`remotecache.vdf` and `remote/save.dat` describe one disposable game. Through
Decky's public legacy RPC, the exact backend discovered the save, backed up
`old`, restored it after the source changed to `new`, then restored the undo.
The test independently read the backup, undo and source bytes at each step.
The runner removed its owned container and image after the test.

The [hosted Decky runtime run](https://github.com/saphid/frame-control/actions/runs/40818938231)
passed the same case on native
[x86_64](https://github.com/saphid/frame-control/actions/runs/40818938231/job/123266572425)
and [ARM64](https://github.com/saphid/frame-control/actions/runs/40818938231/job/123266572719)
at code head `70702b36b66dbee2e6aedaca8c6c85ab6969ad45`. The downloaded reports
record the private byte checks and have SHA-256
`51fa8f8c3f0a486fe6a68adc2ba761a996935748c1208649cfd280a81938e275`
(x86_64) and `890c5a4a561ff272d30dc19cf1f146bb449ea71b67026f3e4b2f3c900c3efc75`
(ARM64).

This proves a bounded private save round trip in published Decky on both
architectures. Automatic backup triggers, real Steam saves, the managed
backend on Frame and worn VR remain unverified. Steamback remains **partial**.
