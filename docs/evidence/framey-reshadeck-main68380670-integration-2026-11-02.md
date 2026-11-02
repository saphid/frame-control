# Reshadeck integration with main 68380670 — 2026-11-02

Implementation `3ab5d33efa9a85559910383c5164c2ecb6e42b3c` normally merges exact main `683806703ec0006764bb6b9c8ddf46d5dab31338` with the previously prepared Reshadeck repair. Six conflicts use exact main plus byte-preserved scoped Reshadeck additions; the helper, private probe, tests and archive retain their reviewed bytes.

The independent source audit retains all **39 main native cases**, adds Reshadeck as case 40, preserves all **116 catalog pins/flags/classifications/policies** and the other 115 complete catalog rows, and checks 1,805 other main git objects. The whole installer/APPLY AST matches main outside store 75, checker outside two Reshadeck branches, runner outside its two added source inputs, and fixture pin inventory outside 75. Main's lifecycle shutdown gate, Discord, Game Sync, ProtonDB and Surround repairs are retained. Generated docs pass.

## Verification

- Complete local unit suite: **2040 tests, 15 platform/optional skips**, 278.649 seconds. These skips do not qualify native or release gates. Unit socket ResourceWarnings are retained in the raw log; the separate e2e suite reports none.
- Complete isolated fake-Frame e2e: **53 tests / zero skips**, all **116 pins** (69 install/remove, 47 expected refusals), zero unclosed HTTP socket warnings. Official backends are stubbed in this suite. Owned Compose resources are gone, image tags restored, and shared simulator identity/start/restart/healthy state preserved.
- Native AMD64 case 75: **15 actual RPCs**, 40 source fingerprints, two strict parent-only clean stops (0.214s / 0.214s); all adopted exits zero, no forced kill or shutdown error.
- Native AMD64 case 14: **9 actual RPCs**, 40 source fingerprints, two strict parent-only clean stops (0.214s / 0.215s); all adopted exits zero, no forced kill or shutdown error.
- Native AMD64 case 37: **14 actual RPCs**, 40 source fingerprints, two strict parent-only clean stops (0.214s / 0.235s); all adopted exits zero, no forced kill or shutdown error.
- Native AMD64 case 100: **20 actual RPCs**, 40 source fingerprints, two strict parent-only clean stops (1.216s / 0.186s); all adopted exits zero, no forced kill or shutdown error.
- Reshadeck's independent native audit verifies all 15 actual RPCs and 13 authenticated private X11 property readbacks, installed backend/shell/helper reconstruction, startup/explicit selection/disable/restart behavior, bounded refusals, both private child-peer EOF and regular stops, shared shader bytes/inode/mode/mtime and unrelated-sibling preservation. Xvfb does not expose the host display and does not render shaders.

The compressed packet includes complete raw reports, consoles, test logs, catalog outcomes, source bindings and independent audit programs. Publication adds only this note, JSON summary and raw packet after the tested implementation. Fresh exact-publication hosted CI, both native architectures, all nine artifact audits and exact-current-main qualification remain required before merge. This is not release qualification.

## Limits

Exact cached store **75 / Reshadeck 0.2.0**, ZIP `f7f79c3f5d12d92d14adfdebad62053d6e10982fb7b662b6777cb06945dc4281`; no fresh live-store version claim. Compatibility stays **partial**. Update/reinstall is required. Requires installed `xprop` and authenticated `DISPLAY`; getter is last successful in-process selection, not compositor state or restart persistence. Actual Frame dependencies, gamescope shader rendering, official UI, Steam CEF, ARM64 at this publication, wearer/controller behavior remain unverified. No real Frame, schedule, security setting, pre-existing data or PR #113 changes.
