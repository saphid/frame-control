# Virtual Surround Sound with ScreenSaver main integration

PR #539 normally integrates main `ad070b731386dfbc2c8ed24b901b0b5edaeacbf2` (ScreenSaver). Tested implementation: `712edcc1ee1f5884869b2f4aa461804a09f2b8a9`; only evidence follows it. The Surround helper, its native probe and nine focused tests remain byte-identical to prior published head `eccb097cc8b2c5f5e0da94b5a450142bcb00714b`.

The shared installer, native runner and exact fixture pin module had merge conflicts. Resolution keeps both independent exact-archive repairs. A local resolver mistakenly left conflict markers in the pin module and a local merge commit was made before the failed audit stopped the sequence. A follow-up commit fixes it before publication, without rewriting history. No tests from the invalid intermediate source count as verification. The first independent verifier also expected 32 source entries instead of 33; the actual difference is exactly the ScreenSaver helper and native fixture. Corrected assertions pass the unchanged runtime reports; the failed count assertion is retained.

## Verification

- **135 focused tests / zero skips**, covering Surround, ScreenSaver, Animation Changer, native inventory, store transactions and compatibility. Generated docs and diff checks pass.
- Whole installer module/APPLY and checker ASTs retain current main behavior outside the exact Surround additions. All **36** main runtime cases, all **116** archive pins/flags/classifications/install policies and the other **115** complete catalog rows are retained. Another **1,742** existing main files match byte-for-byte.
- **Native AMD64, published Decky 3.3.0, Surround:** **20 actual RPCs**, **33 source bindings**, exact archive/managed backend/helper reconstruction, private Pulse stream routing both ways, six/eight-channel preset readbacks, owned filter recovery, settings restart and **two strict parent-only clean stops**. Shared HRIR/unit marker bytes and inode/mode/mtime, plus an unrelated sibling, survive. Speaker-test channels **1 and 2** were observed before owned cancellation and reaping; the complete all-channel sequence is unverified.
- **Same combined source, ScreenSaver regression:** **31 actual RPCs**, **14 independent dbus-python client calls**, positive inhibitor cookies/events, three APIs and the ScreenSaver alias, existing-name refusal without queued takeover, client-disconnect release, settings/marker/sibling preservation and **two strict parent-only clean stops**. The plugin uses unchanged vendored dbus-next; these are retained call/reply records, not raw D-Bus packet capture.
- The preceding published head `eccb097...` had all **18** triggered checks green, both hosted native architectures and **53 e2e tests / zero skips** (official backend execution stubbed). Its four Syncthing package regression modes were independently audited against 160 sources and 1,405 source hash bindings. Those records qualify that prior head only and do not qualify this integration. These package fixtures do not prove Surround UI or physical audio.

The adjacent compressed evidence retains current native reports/consoles, independent readback/source audits, focused output, the initial count assertion and the old-head package inventory/qualification. Scoped strict stop assertions pass; the generic console wrapper still reports global-clean false. No complete host filesystem/process snapshot was taken.

## Limits

Fresh exact-head hosted CI/e2e/native ARM64 and ownership/package qualification remain required before merge. No fresh browser, Steam CEF, Frame dependencies/audio, audible quality, actual suspend inhibition, official UI or wearer/controller proof. Compatibility remains partial. No headset, security, schedule or pre-existing data changes; no release qualification.

## Announcement

Virtual Surround Sound's private-file and owned-process repair is integrated with the current ScreenSaver main changes. Combined-source native AMD64 tests verify private audio routing and D-Bus state/cleanup. Update/reinstall is required for the managed repair. Actual Frame audio, suspend inhibition, official UI and wearer/controller behavior remain unverified.
