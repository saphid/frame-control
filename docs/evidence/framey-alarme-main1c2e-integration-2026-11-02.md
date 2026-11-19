# AlarMe restart and shutdown integration — 2026-11-02

Implementation `4b936a59dd8681c5c7cdfc2cda7e582f77befcce` normally integrates current main `1c2e48c89f031ae70136106c1de3ba556a4c6c74` with the
published #545 IPC repair and its #496 paused-timer dependency. The runtime input, negative-control and e2e conflicts retain all three plugin
sets and probes; the compatibility table was regenerated from the merged catalog. All **40 main native cases**
remain; AlarMe is case 41. The installer/APPLY, checker, e2e and store-test ASTs
outside AlarMe match main. All **116 pins, flags, policies and ratings** and the
other **115 complete catalog rows** remain. The shared IPC adapter, primary
shutdown gate, previous AlarMe native probe and exact official ZIP are unchanged.
Generated docs and diff checks against current main pass. Main’s Download All
and LocalSend child EOF repair blocks, negative controls and e2e receipts are
retained unchanged.

## Verification

- Complete unit suite: **2046 tests**, **15 platform/optional
  skips**, 281.27s. ResourceWarnings remain in raw unit evidence;
  skips do not qualify native or release gates.
- Published Decky **3.3.0 native AMD64**: **39 managed / 38 original API1 RPCs**,
  all 77 response matches, exact independently reconstructed backends, private
  silent timer events, and original paused/elapsed-deadline failures retained.
  Two strict managed parent-only stops take **0.225s / 0.215s**,
  including a real child Unix peer EOF before the first stop. No forced child
  kill, shutdown error or exact surviving descendant; adopted child exits are
  zero and unload callbacks are observed. All **43 source fingerprints** bind
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

[Bound summary](framey-alarme-main1c2e-integration-2026-11-02.json) · [Raw observations and verifiers](framey-alarme-main1c2e-integration-2026-11-02-raw.json.gz).
