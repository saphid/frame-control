# Reshadeck preservation with ScreenSaver main — 2026-11-01

Implementation `f1d6b708a6bdbb43ea7e38b3c0a114e91700942e` normally merges exact main `ad070b731386dfbc2c8ed24b901b0b5edaeacbf2` into prior Reshadeck head `25a7fbf2ef479aae84a6c036cc662eb8930e0472`. Seven conflict files retain both digest-scoped installer repairs, both runtime fixtures, all 36 existing main cases, all 116 archive pins/policies/classifications and the other 115 complete catalog rows. The original Reshadeck helper, probe, unit tests and ZIP are unchanged. Whole installer/APPLY, checker, runner and inventory ASTs outside Reshadeck match main; all other 1,742 main Git objects are unchanged. Generated docs pass.

## Combined-source verification

- **128 focused tests / zero skips**: Reshadeck, ScreenSaver, installer transactions, compatibility, native inventory, archive inventory and IPC EOF.
- Published Decky 3.3.0, native AMD64 Reshadeck: **15 RPCs / 13 independent private authenticated X11 property readbacks**. Startup preserves the unmanaged effect; explicit bundled/custom/screensaver/disable choices work; invalid choices preserve the property. Shared marker bytes/inodes/mode/mtime, installed backend/helper hashes and an unrelated sibling are checked. Two strict parent-only stops, including real child IPC EOF, complete in 0.215s/0.214s without forced kill. These marker/property tests do not prove visible shader rendering or compositor-state reporting.
- Same-source ScreenSaver: **31 RPCs / 14 independent dbus-python calls** against unchanged vendored dbus-next. Existing name ownership is preserved without queueing, all three inhibit APIs work privately, disconnect releases the inhibitor, settings survive restart, and two strict parent-only stops pass. Actual suspend inhibition and official UI remain unverified.
- Both native reports bind the same **33 source hashes**. Generic recorder clean-shutdown flags remain false; the explicit, independently audited stop records supply scoped evidence.
- Full fake-Frame simulator: **53 tests / zero skips** in **411.391 seconds**, all **116 exact catalog pins**, **69 install/removes / 47 expected refusals**. Official backend execution is stubbed. All owned Compose containers, volumes and networks are gone; prior image tags are restored and the shared simulator is unchanged and healthy. The retained main fixture still emits 2 socket ResourceWarnings; #544 separately addresses those listeners.

## Prior evidence and limits

Prior head `25a7fbf2ef479aae84a6c036cc662eb8930e0472` passed all 18 hosted checks. Both hosted AMD64 and ARM64 Reshadeck case records are independently audited: 15 RPCs, 13 property readbacks, shared-file preservation and two strict stops per architecture. Artifact ZIP digests, exact logged checkout and all 31 source hashes match. Not every producer case is independently behavior-audited.

All four prior-head signed-package modes are independently audited, with 160 distinct sources and 1405 hash bindings. These native/package results qualify only that older source; fresh exact-publication hosted CI/e2e/native ARM64 and every triggered ownership/package gate are required. Exact current-main green, feedback and mergeability are also required.

Compatibility remains partial. xprop and an authenticated DISPLAY must exist; shader directory parents must not be symlinks. Failed commands retain the plugin process's last successful selection; its getter is not compositor-state or restart-persistence proof. Actual Frame dependency/display integration, gamescope rendering, official UI/Steam CEF and wearer/controller usability remain unverified. No headset, schedule, security setting or pre-existing user data was touched. Syncthing stays disabled; no merge or release is qualified.

[Summary](framey-reshadeck-mainad070-integration-2026-11-01.json) · [Raw observations, logs and verifiers](framey-reshadeck-mainad070-integration-2026-11-01-raw.json.gz).
