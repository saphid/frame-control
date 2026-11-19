# AlarMe restart and shutdown integration — 2026-11-02

Implementation `49ed48fc1972731f339f3066d414dac4ac624c6a` normally integrates current main `84f5efd3fbde8525b473f11c3bd2071d7ffb3e82` with the
published #545 IPC repair and its #496 paused-timer dependency. Three inventory
conflicts retain both plugin sets and probe names. All **40 main native cases**
remain; AlarMe is case 41. The installer/APPLY, checker, e2e and store-test ASTs
outside AlarMe match main. All **116 pins, flags, policies and ratings** and the
other **115 complete catalog rows** remain. The shared IPC adapter, primary
shutdown gate, previous AlarMe native probe and exact official ZIP are unchanged.
Generated docs and diff checks against current main pass. A diff check against
the old branch flagged only two pre-existing main EOF blank lines; their exact
bytes were retained.

## Verification

- Complete unit suite: **2043 tests**, **15 platform/optional
  skips**, 278.25s. ResourceWarnings remain in raw unit evidence;
  skips do not qualify native or release gates.
- Published Decky **3.3.0 native AMD64**: **39 managed / 38 original API1 RPCs**,
  all 77 response matches, exact independently reconstructed backends, private
  silent timer events, and original paused/elapsed-deadline failures retained.
  Two strict managed parent-only stops take **0.214s / 0.214s**,
  including a real child Unix peer EOF before the first stop. No forced child
  kill, shutdown error or exact surviving descendant; adopted child exits are
  zero and unload callbacks are observed. All **41 source fingerprints** bind
  the combined implementation. Earlier deterministic red and failed ARM64
  evidence remain retained; this AMD64 pass does not replace them.
- Complete disposable fake-Frame e2e: **53 tests / zero skips**, all **116 pins**
  (**69 install/removes / 47 refusals**), zero unclosed HTTP socket warnings.
  Official backends are stubbed. Owned Compose resources are gone, prior image
  tags restored and the shared simulator identity/start/restart/healthy state
  preserved.

## Limits

Fresh exact-publication hosted tests, both full primary native architectures,
strict AlarMe shutdown on ARM64, both ownership/service artifacts and all four
signed-package modes remain required. No browser replay, real Steam CEF, sound,
actual sleep inhibition, Frame or wearer/controller proof is added. Catalog
compatibility stays partial and installed copies require Update/reinstall.
Scope cleanup observations do not establish a globally clean host. No real
headset, schedule, security setting or pre-existing data was changed. No merge
or release is qualified by these local checks.

[Bound summary](framey-alarme-main84f5-integration-2026-11-02.json) · [Raw observations and verifiers](framey-alarme-main84f5-integration-2026-11-02-raw.json.gz).
