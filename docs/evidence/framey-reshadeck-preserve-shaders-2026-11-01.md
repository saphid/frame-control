# Reshadeck shared shader preservation — 2026-11-01

Implementation `3028be8877f6837fdc1442bc98f8bf6171634f32`; test-root fixture revision `08332cf2d927ba189c3255b91a62c71068b03d7e`;
base main `89757d33f61124486404bc16e84b7d3697cf2c9f`. Exact store **75 / Reshadeck 0.2.0**, ZIP
`f7f79c3f5d12d92d14adfdebad62053d6e10982fb7b662b6777cb06945dc4281`;
original backend `ff5b902a09892638b2a7f3ff784fe57211f7ab7ad1a63ffa0bdfa9e3c47cdb56`.

The published startup overwrote bundled shader filenames in the user's shared
gamescope shader directory and applied its default disable effect. A disposable
fixture reproduces the overwrite. The scoped adapter preserves original backend
bytes inside its helper hooks, retains every other archive member, exclusively
publishes only missing .fx/.fxh files, and never replaces existing filenames or
symlinks. Startup deploys missing files but leaves the active effect alone.
Unload/uninstall retains shader files. Explicit basename selections, including
custom filenames with spaces, use one direct bounded xprop command with the
actual DISPLAY. Missing/invalid/symlink files are refused; failed commands keep
the last successful in-process selection. Screensaver selection only records
until explicit apply. The current getter is not compositor state or restart
persistence. Shader directories must have no symlink parents.

## Verification

- Nine focused tests, three native inventory tests, 25 compatibility tests and
  18 site tests pass. Full unit suite: **1984 tests, 15 platform/optional
  skips**, 254.333 seconds. This full run uses the implementation source before
  the test-root-only normalization; production/native inputs are unchanged.
- A private symlink temporary-root fixture reproduces seven original errors;
  the normalized test root passes **nine / zero skips** while symlink refusals
  remain tested. It fixes macOS's temporary path alias in the host fixture,
  without weakening the Linux production guard. A hosted macOS rerun is pending.
- Published Decky **3.3.0 native AMD64**, networkless/device-free: **15 actual RPCs**
  and **13 independent X11 root-property readbacks** on private authenticated
  Xvfb. Startup retains an unmanaged property; explicit bundled/custom/screen-
  saver/disable choices work. Invalid, missing and symlink choices leave the
  property unchanged. Restart leaves the selected effect in place.
- Two separately verified strict parent-only loader stops exit zero without
  forced plugin kills, including one controlled Unix EOF. Exact descendants
  disappear, adopted exits succeed, and an unrelated sibling survives. Shared
  shader marker bytes/inode/mode/mtime remain unchanged. The generic recorder
  does not certify plugin clean shutdown; those two scoped stops do.
- Installed backend, shell and both helpers independently match expected bytes.
  All **29 native input hashes** match the fixture revision. The independent
  source audit preserves the whole installer/APPLY AST outside exact store 75,
  checker outside its two fixture branches, all 34 previous native cases and
  **1,720 other existing main files**. Other 115 complete catalog rows match;
  all 116 pins, flags, classifications and install policies remain unchanged.
- Isolated fake-Frame e2e passes **53 tests / zero skips** in
  **405.496 seconds**: all 116 pinned archives, 69 install/removes,
  47 expected refusals. Official backends are not executed by that suite. Its
  recorded source is the implementation before the test-only root change.
  Owned temporary/Compose resources are gone, image tags restored and the shared
  simulator identity/start/health retained. Socket ResourceWarnings remain.

The first native fixture attempt failed because Xvfb reset root properties
when its last short-lived xprop client disconnected. The fixture now uses
-noreset while keeping authentication and no TCP/host display access. Failed
logs and empty-case result are retained separately; they are not counted as a
product pass. Final native and raw-console proof is independently audited.

## Limits

This controls gamescope's ReShade X11 property; it does not deploy into Proton
prefixes. Runtime requires installed xprop and an authenticated DISPLAY. Those
dependencies on the actual Frame, real gamescope shader rendering, rendered
Decky controls, ARM64, real Steam CEF and wearer/controller behavior are
**unverified**. Marker shaders in Xvfb are private bytes, not valid renderer
proof. Compatibility stays **partial**. No real Frame, schedule, security
settings, user data or PR #113 was touched. Main's nine checks and both native
automated artifacts/e2e pass at the stated base; fresh exact-publication CI,
native ARM64 and applicable ownership/package gates remain required. No merge
or release is qualified by these local checks.

The JSON and compressed packet retain raw RPCs, X11 values, consoles, process
and file observations, test logs, first failed fixture and audit programs.
