# Wine Cellar 0.2.1 managed bridge candidate, 29 October 2026

Wine Cellar is **partial** only for the scoped behavior below. The official
0.2.1 ZIP remains x86-64. The exact-digest Framey installer can replace its
helper with a pinned ARM64 build and run a managed Python backend whose
fixed-origin WebSocket connection is reachable only through the plugin's
receipt-bound panel method calls. The Rust helper's original Steam origin
check remains intact. Existing installs need update or reinstall.

## Exact inputs

- Official ZIP SHA-256: `7e077b933c234414d172b5c6d1c804b026bf39fa4e18e6663495a282637031e8`.
- Official helper SHA-256: `7796bfc96d466824617b2fee96dc1bc4beda30c776a9c61e0cc168d3473d29fe`.
- Managed ARM64 helper SHA-256: `d668a9ac02ccce97cf601bcff86f0b2104ee85e6a1105499e66178d9d19b64a8`.
- Managed Python source SHA-256: `44841fea9318bb975aebaf1024ad14c912e5d5fe8b6fef561671e6a0e9559411`.

The [earlier feasibility probe](framey-wine-cellar-arm64-2026-10-29.md)
records the source tag, build recipe, upstream Rust tests, and a locked,
read-only ARM64 helper run on the real Frame. This candidate did **not** run
its managed plugin on the real Frame or access the headset.

## Checks completed before PR

- All 1,757 Python tests passed with 16 skips after the final source/hash
  update. Focused store, panel, socket, runtime inventory and browser-audit
  tests passed 91/91.
- The exact official ZIP passed the managed installer unit flow. It rejects a
  different digest, source, frontend or architecture. A receipt check rejects
  stale or wrong-plugin socket calls before CEF access.
- Published Decky 3.3.0 on isolated AMD64 and native ARM64 discovered the
  managed plugin, spawned the matching helper against a private empty Steam
  home, and answered a read-only `GetState` with zero installed tools. Both
  probes closed the socket. The AMD64 JSON result is
  `/tmp/framey-wine-decky-runtime-20261029-mppkd9qczt.json` on the test host.
  The [ARM64 hosted job](https://github.com/saphid/frame-control/actions/runs/40952094213/job/123722554018)
  passed Wine Cellar case 68 on PR head `035baa9350959fbb1faaf805cf4afb93765d7845`.
- Local Chromium ran the exact official frontend in an opaque iframe with a
  fixture shaped like that empty native state. Dashboard displayed “No
  installed compatibility tools are available.” The Applications view
  reported the deliberately denied live Steam library read. The fixture
  rejected tool commands, fetches and network access. See
  [browser capture](framey-wine-cellar-browser-2026-10-29.png).

The first hosted fake-Frame e2e run passed the generic pinned official
install/remove flow on PR head `035baa9350959fbb1faaf805cf4afb93765d7845`.
A stronger Wine Cellar specific receipt/helper-hash assertion has been added
for the next head and is **pending**. The local e2e launcher needs `zsh`,
which is unavailable on this test host; its failure to launch is not an e2e
pass.

## Remaining limits

No Wine compatibility tool was downloaded, installed, removed, selected, or
used to start a game. The exact frontend's private empty state is the only
rendered panel result checked here. A nonempty real Steam library, live
catalog, real Frame managed Decky service, installer UI, worn VR visibility,
and physical controller use remain unverified. The companion fake-Frame CI
proves transport and rollback only; it cannot prove these live behaviors.
