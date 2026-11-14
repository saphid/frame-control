# Steam Status child IPC EOF — 2026-11-02

Exact implementation `2bf45b2f4bc352eb470c84966cb831da3a24834d` repairs only cached store **123 / Steam Status 1.2.3**
ZIP `9053308e04a74f44745b45b9f4f50af3673348d367e7b14bacc5677de707ac4e`.
The two existing verified TLS contexts retain their exact prior managed bytes;
the shared child-local EOF adapter is prefixed and delivered atomically. Missing
payloads refuse installation, changed archives get no adapter, and other archive
files retain exact bytes. Compatibility stays partial; Update/reinstall is required.

## Failure and validation

- Parent #496 head `4d1168bf` failed ARM64 job **125168806989**: its loader exited
  zero after forcibly killing Steam Status. Artifact **13125973234**, SHA-256
  `773abc6826694f14cf4c561d4c55e15119b21602f5b3df21402b682b4f46bb56`,
  exact job checkout and all committed source fingerprints are retained.
- Local pre-repair commit `bf97c3c11aebbfa5335f039d5edcfea77823037e` reproduces real Unix-peer EOF,
  failed RPC readback and forced plugin kill. The original strict gate rejects it.
- Published Decky **3.3.0 native AMD64**: **five managed / three prior-managed RPCs**;
  settings survive EOF and restart. Two parent-only clean stops take **0.214s /
  0.235s** with original unload callback, zero adopted-child exits and no exact
  surviving descendant. An unrelated sibling and private marker survive. Removing
  only the adapter preserves verified TLS bytes and deterministically reproduces
  the **5.224s forced kill**. All **43 source fingerprints** match committed objects.
- **79 store unit tests / zero skips** and **three runner-coverage tests** pass,
  including missing-payload refusal and no adaptation for changed archives.
  Initial receipt-schema and discovery-fixture assertion failures are retained;
  they were corrected rather than counted as passes.
- Source/AST audit preserves the other **39 native cases**, other **115 full
  catalog rows**, all **116 pins/flags/policies/ratings**, all other installer,
  checker, e2e and store-test behavior, shared adapter and strict producer gate.
  Generated docs, compilation and diff checks pass.

## Limits

Fresh exact-publication full CI, e2e, native ARM64 and AMD64 inventories, both
ownership/service artifacts and all four package modes remain required. No public
network diagnostics, new browser replay, real Frame, wearer/controller proof or
release qualification. Historical TLS/persistence evidence does not qualify this
new EOF repair. No headset, schedule, security setting or pre-existing data changed.
Cleanup observations are scoped to the private fixture, not the entire host.

[Summary](framey-steam-status-ipc-eof-2026-11-02.json) · [Raw observations and verifiers](framey-steam-status-ipc-eof-2026-11-02-raw.json.gz).
