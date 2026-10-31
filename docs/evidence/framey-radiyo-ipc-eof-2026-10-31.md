# RadiYo: clean shutdown after a child IPC disconnect

RadiYo! 1.3 (store 24, archive SHA-256 `647111578aa7a5ecd16af8d7fe6c068a6d7ea8737c6dce5ac2d52e84a549ec43`) could pass HTTP RPC probes while requiring Decky's five-second plugin SIGKILL during unload. The retained ARM64 console from [run 41188680065](https://github.com/saphid/frame-control/actions/runs/41188680065/job/124500753877) shows this failure. A fresh isolated AMD64 baseline with main0082d79's production installer reproduces it after an explicit private Unix-peer disconnect.

Install the existing child-local EOF adapter only in this exact managed archive. It stops dispatching a disconnected peer so the child can exit normally. Removing the three import/install lines restores the exact prior managed backend SHA-256 `79d14191b83345caedeb7a819c283f495ce6f5923fd81d1aecb86c14254a6be3`. Both existing verified-TLS adaptations and the shared adapter are unchanged. Existing managed copies need Update/reinstall; compatibility remains partial.

## Verification

Source `f7748f22229df6f3ab2ce3dccb93d3164468d933`, based on main `0082d79a3ff9a9338e49dd5c83bbe25aa9e784b4`:

- 85 focused installer, compatibility, runtime-inventory and IPC tests pass. Generated compatibility documentation and diff checks pass.
- A fresh native AMD64 replay uses digest-pinned published Decky 3.3.0 (`e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181`). All 16 native source fingerprints independently match this source. All 16 baseline fingerprints match committed baseline `8ddb3881`, whose production installer bytes match main.
- The repaired case performs nine authenticated legacy RPCs: loopback HTTP station/custom fetch and redirect, both self-signed HTTPS rejections, and loopback fetch/redirect before and after loader restart. The first stop follows an explicit private peer disconnect; the second is a natural parent-only stop. Both loader exits and recorded adopted-child exits are zero, recorded descendant identities disappear, no plugin SIGKILL/shutdown diagnostic is observed, and an unrelated sibling survives.
- A separate disposable container restores the prior managed backend by hash. Seven RPCs, including both self-signed HTTPS rejections, still pass, followed by the expected five-second plugin SIGKILL. This retained negative control is not a compatibility pass.
- Independent checks verify each literal method sequence and station body, loopback redirect targets, HTTP readbacks, certificate rejection strings, raw console hashes, owned process identities and stop records. All original archive members except the previously adapted backend are byte-preserved; the TLS-adjusted backend differs only by the new IPC prefix.
- All 116 status/install policies, the other 115 complete catalog rows, the other 33 native cases and 36 other probe/setup bodies are preserved. The hosted full matrix will contain 42 probes / 34 archive pins / 16 source fingerprints per architecture.

[Independent audit](framey-radiyo-ipc-eof-2026-10-31.json) · [raw final/baseline reports, complete available consoles and test output](framey-radiyo-ipc-eof-2026-10-31-raw.json.gz).

## Limits

This is isolated AMD64 fixture evidence. Fresh exact-head hosted checks/e2e, AMD64/ARM64 native runs, every triggered package mode, exact current-main integration and feedback review remain required. The explicit disconnect stabilizes the observed shutdown race; it does not measure real-use frequency. Scoped stop evidence does not establish global clean plugin shutdown.

No new browser, external station, trusted HTTPS, audio playback, real Steam CEF, managed Frame installation, wearer-visible or physical-controller usability is proved. No headset or hourly schedule was accessed. Other plugins' lifecycle work remains separate. No release is qualified or published.

## Installer receipt regression coverage

Tested source `f3b84655c868f63d33a773c79bd30cddc58eded1` adds HTTP/SSH installer assertions for the exact RadiYo TLS/IPC receipt, API shim list, partial compatibility status, installed backend SHA-256 `23cdff5bfa7f57e6c0341c825ab23cfb363e4408ae3c4f117fe3d1885f00a265`, and shared IPC helper bytes. Production and all 16 native probe source fingerprints are unchanged.

A fresh owned fake-Frame run passed `test_pinned_official_plugins_install_and_remove`: one method, 37 pinned plugin fixtures, zero skips, 80.272 seconds including setup. All owned containers, volumes, network and images were removed. This checks installation bytes, receipts, frontend/manifest files and removal; the fake Frame does not execute official backends. The full e2e suite and optional 116-plugin catalog audit were not run locally.

The previous hosted native run [41191858034](https://github.com/saphid/frame-control/actions/runs/41191858034/job/124510088087) at `e1e4dcbc` failed in the ARM64 positive DeckyParty reload probe after a forced plugin kill and reload timeout. The retained partial report completed seven probes and did not reach RadiYo. Existing repair #518 owns that failure; it is not waived or counted as a RadiYo pass. Every fresh final-head hosted gate remains required.

[Receipt-test audit](framey-radiyo-receipt-e2e-2026-10-31.json) · [complete local log, test source and retained prior failure](framey-radiyo-receipt-e2e-2026-10-31-raw.json.gz).
