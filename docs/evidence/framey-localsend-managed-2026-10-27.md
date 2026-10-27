# Decky Localsend managed ARM64 candidate, 27 October 2026

Official Decky Localsend **0.4.5**, store ID **125**, archive SHA-256
`e271ccb55eb23f918b99a69f79aec905df4c9b2ef7b23bbf4ec1c2d1a6f0c6b7`,
contains an x86_64 helper. Frame Control's proposed managed adaptation accepts
only that exact archive. The original x86 helper and Python backend hashes are
checked before a pinned static ARM64 helper replaces the binary. The headset
transaction checks the ARM64 SHA-256 and ELF machine again. It leaves the
official Python, frontend, manifest and BSD license unchanged, retains
managed update/remove receipts, and rejects changed archive digests.

[Source correspondence and local upstream transfer](framey-localsend-source-match-2026-10-27.md)
records the exact upstream plugin tag and Go commit. The native asset and
build recipe are [bundled](../../ui/vendor/localsend-0.4.5/README.md).
Go dependencies are checksum-pinned but not vendored. The Frame installer
does not download modules or run a compiler.

## Evidence so far

- The host transaction tests installed and removed the exact archive,
  preserved its Python/LICENSE bytes, checked the managed receipt and
  rejected a changed archive. The ARM64 branch independently wrote and
  hashed the AArch64 ELF on x86 without executing it.
- The fake Frame managed install/remove flow passed with the exact official
  archive and checked the installed helper digest. Its project containers,
  volumes and network were absent after the run.
- The full local Python suite passed **1,669 tests with 16 skipped** after
  rerunning with loopback socket access. The first attempt ran inside a
  workspace sandbox that denied local test sockets across unrelated server
  tests; it did not identify a LocalSend regression.
- A fresh local Chromium opaque iframe initialized the exact official frontend
  with backend and network effects denied. Its visible text included Backend is
  stopped, Device Name, Available Devices, File Upload, Receive History and
  Configuration. The initializer reported ready and called only
  `get_receive_history`, `get_backend_status` and `get_backend_config`.
  This proves a visible initial panel with safe fallbacks, not working send,
  receive or settings controls.
- The original x86 backend and helper completed one private no-route marker
  transfer outside Decky. This does not prove the managed ARM64 binary or
  actual Decky service.
- A locked real Frame probe ran the rebuilt ARM64 helper with SHA-256
  `e20363237e606ee65eae857792176d21a0bb8ba863489952728eaf2b13277dae`
  in a private network namespace with no default route. Its LocalSend 2.0
  endpoint accepted and saved one 38-byte marker, and the saved bytes matched
  the sent marker. The headset was in standby (SteamVR activity 3, proximity
  raw 4.6875) with 72% battery before and after. Both normal Frame Control
  services stayed inactive. The owned helper/process/files and shared lock
  were removed. [Machine-readable result](framey-localsend-arm64-transfer-2026-10-27.json).

The published Decky 3.3.0 native AMD64 and ARM64 discovery/status/configuration
gate and a useful frontend workflow still need verification before this
candidate can merge or ship. The ARM64 marker test exercised the helper in
isolation, not the actual Decky plugin service, local discovery, user-facing
transfer, or installation on the headset. No worn visibility or physical
controller claim follows from this candidate.

The proposed catalog status is **partial** for exact managed archive
installation and settings/status. Steam routes, local discovery, user-facing
transfer, clipboard/screenshot sharing and worn VR remain unverified. The
historical raw-archive audit fields still describe the earlier unadapted x86
ZIP; `managedNative` records the current digest-scoped path separately.
