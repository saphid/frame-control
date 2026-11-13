# SuggestMe child IPC EOF — 2026-11-02

Exact implementation `45db11f2c3337e3903fa9f41c7d6232e2522ac64` adds the SuggestMe repair above the separate
Steam Status PR #553. Only cached store **132 / SuggestMe 1.5.3** ZIP
`248294b5d6b9d5a5d635ce35f4b5185ce59d4e4fd59353e24df4b29d74c2ade4`
gets this adapter. Existing verified TLS-fallback bytes are preserved exactly;
the unchanged shared child-only EOF adapter is prefixed and delivered atomically.
Missing payloads refuse installation, changed archives get no adapter, and all
other archive files retain exact bytes. Compatibility stays partial; existing
copies require Update/reinstall. No fresh live-store claim.

## Failure and validation

- Parent #496 head `4d1168bf` failed AMD64 job **125168807082**: the loader exited
  zero after a five-second forced plugin kill. Artifact **13126550891**, SHA-256
  `3e9ccfdf1e0011aa22d5a31cf728ffcc5a707363301ad9c06d919dc9e9538217`,
  exact producing job checkout and all committed source fingerprints are retained.
- Local pre-repair commit `418a382d3fdaafe96a62d94caf9b54a2140e51b0` reproduces real Unix-peer EOF,
  failed RPC readback and forced plugin kill; the strict gate rejects it.
- Published Decky **3.3.0 native AMD64**: **eight managed / six prior-managed RPCs**;
  empty-library defaults and private filter preset survive EOF and restart.
  Two parent-only clean stops take **0.195s / 0.214s**, with original
  unload callback, zero adopted-child exits and no exact surviving descendant.
  Unrelated sibling and marker survive. Removing only the adapter retains verified
  TLS fallback bytes and reproduces the **5.245s forced kill**. All **44 source
  fingerprints** match committed objects.
- The same combined source independently rechecks Steam Status: **five managed /
  three prior-managed RPCs**, peer EOF readback, restart and clean parent-only stops
  (**0.225s / 0.185s**), plus its explicit forced-kill control.
- Complete local unit suite: **2048 tests / 15 platform or
  optional skips**, 279.977s, on `844211b6f6a62c0152894f30e194debedc60fccf`. The only
  later implementation change consolidates SuggestMe e2e receipt assertions;
  all production, unit and native input bytes are unchanged. ResourceWarnings
  remain in raw evidence; optional skips do not qualify native or release gates.
  Runner coverage also passes. Initial full-unit and e2e failures from stale
  TLS-only receipt fixtures are retained; corrected fixtures require both shims.
- Complete disposable fake-Frame e2e: **53 tests / zero skips**, 414.625s,
  all **116 pins / 69 install-removes / 47 refusals**, zero unclosed HTTP socket
  warnings. Official backends are stubbed. Owned Compose resources are removed,
  previous image tags restored and the shared simulator unchanged and healthy.
- Source/AST audit retains the other **39 native cases**, other **115 full catalog
  rows**, all **116 pins/flags/policies/ratings**, parent Steam Status repair, all
  other installer/checker/e2e/store-test behavior, shared adapter and strict gate.
  Generated docs, compilation and diff checks pass.

## Limits

Fresh exact-publication full CI/e2e, AMD64/ARM64 native inventories, both
ownership/service artifacts and all four signed-package modes remain required.
No Steam credentials, real library recommendations, public network requests,
new browser replay, Frame or wearer/controller proof. Historical persistence/TLS
passes do not qualify this new EOF repair. No headset, schedule, security setting
or pre-existing data changes. Cleanup claims are scoped; no merge or release is
qualified by these local checks.

[Summary](framey-suggestme-ipc-eof-2026-11-02.json) · [Raw observations and verifiers](framey-suggestme-ipc-eof-2026-11-02-raw.json.gz).
