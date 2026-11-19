# AlarMe repair with Volume Mixer main — 2026-11-01

Local verification integration `7766f6006df6a39315e6f11a6317a46d66fc90d9` normally merges the published #545
repair `ee627904d8f8985f50257e8f66f0be9cbdae4cee` with main
`a963dc2920231448353e7cc0fb03ae9c519c0aaf`. This local integration is preparation
for #496 after #545 qualifies; it does not merge the unqualified repair into
main or waive its hosted gates.

Two inventory conflicts retain both exact plugins. All **37 main native cases**,
**116 pins/policies/ratings** and **115 other complete catalog rows** remain.
Whole installer/APPLY, checker, e2e and store-test ASTs outside AlarMe match
main. The AlarMe probe/archive and Volume Mixer inputs are unchanged. Generated
docs and source/diff checks pass.

## Verification

- **89 focused tests / zero skips**: store transactions, child IPC, Volume Mixer
  and native inventory.
- Native AMD64, published Decky 3.3.0: AlarMe **39 repaired / 38 original API1
  RPCs**, all 77 response matches, exact reconstructed backends, silent timer
  events, and retained original paused/elapsed-deadline failures. Strict managed
  parent-only stops take **0.195s / 0.214s**, including an actual child Unix peer
  EOF in the first. No forced child kill, shutdown error or exact surviving
  descendant; adopted exits are zero and unload callbacks are present.
- Same-source Volume Mixer: **12 legacy RPCs**, four independent stereo pactl
  readbacks, preserved unrelated stream/process/marker, stopped-stream removal,
  restart and two strict stops. Its original wrong-user Pulse connection
  failure remains required. Both reports bind the same **33 source hashes**.
- Complete native consoles retain the known JSON diagnostics; generic
  global-clean flags remain false. This is scoped shutdown evidence, not an
  independent complete filesystem-preservation claim.
- Full disposable fake-Frame e2e: **53 tests / zero skips**,
  **413.332 seconds**, all **116 exact pins**, **69 install/removes**,
  **47 expected refusals**. Official backend execution is stubbed. Owned
  containers, volumes and networks are gone, prior image tags restored and
  the shared simulator unchanged/healthy. Two listener ResourceWarnings
  remain; #544 addresses those separately.

## Limits

Exact published #545 CI, strict native ARM64 shutdown and combined-main hosted
qualification remain required. No real headset was contacted by these tests.
Sound, actual sleep inhibition, browser/Steam CEF, real-Frame adapted backends
and wearer/controller use remain unverified. Compatibility remains partial
for AlarMe; existing copies require Update/reinstall. This does not qualify
a merge or release. The earlier failed ARM64 shutdown, deterministic RED and
first failed e2e are retained in #496/#545's linked evidence.

[Bound summary](framey-alarme-volume-integration-2026-11-01.json) · [Raw observations and verifiers](framey-alarme-volume-integration-2026-11-01-raw.json.gz).
