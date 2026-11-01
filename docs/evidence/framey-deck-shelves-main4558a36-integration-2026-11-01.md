# Deck Shelves: preserve current main's deterministic DNS tests

Prior publication `6c157e6df71000ad7e9cd3a607f09c9d1555a82f` was fully green, but GitHub's merge preview still
used old main `61efc562a65b552b1c00b75e8559c1c78764f57e` instead of current
main `4558a36f58f84840d835f4fc281f12541f15ea94`. That stale preview was not accepted as a current-main merge gate.
Normal, conflict-free integration produces source `33bc70aeff9141484eabe9c4780032f71c24c46d` with direct parents
`6c157e6df71000ad7e9cd3a607f09c9d1555a82f` and `4558a36f58f84840d835f4fc281f12541f15ea94`. No history was rewritten and no live CI sibling was cancelled.

The integration adds only `tests/test_link.py` and main's three DNS evidence
files. The connection test file is byte-identical to current main. All **84
connection tests passed, zero skips**, in 26.060 seconds. Independent
source audits verify the complete current-main installer, checker, e2e and
receipt/store tests outside intended Deck Shelves additions. All **25 native
runtime inputs are byte-identical to the previous publication**, and all 116
compatibility status/install policies are preserved. This is source preservation,
not a new-head native execution. The evidence publication adds only this note,
its JSON summary and compressed packet.

## Previous exact-head qualification

These results execute **prior publication `6c157e6df71000ad7e9cd3a607f09c9d1555a82f`**, not the new integration:

- Hosted native Decky 3.3.0: **51 producer cases per architecture** on AMD64 and
  ARM64, all 25 source fingerprints. Eight independent behavior audits cover
  Deck Shelves 4/3 RPCs, SteamGridDB 14/12, RadiYo 9/7 and Prefix Manager
  39/42/40 per architecture. Not every producer case has an independent behavior
  audit. Deck Shelves verifies controlled EOF, original unload hooks, clean
  parent-only stops, private settings/backup preservation and post-restart RPC.
  No RPC between EOF and shutdown is claimed.
- Hosted ARM64 Fake Frame: **53 tests, zero skips**, all **116** catalog pins
  and expected install/refusal outcomes verified. This transport suite does not
  execute every official backend. The successful job retains its cleanup trap;
  no independent post-job Docker resource inventory was captured.
- Ownership/runtime/service artifacts on **both architectures** verify actual
  two-way sync, strict actual-user service shutdown and source-bound producer
  ownership controls; each architecture passes five classifier and eleven
  owned-unit tests including a real TIME_WAIT control. No independent process
  state capture beyond producer assertions is claimed.
- All **four signed-package modes** independently audited: AMD64 base, ARM64
  base, browser HTTP and production-parent HTTP. Exact ZIP/member digests,
  checkout logs, **154 unique sources and
  1373 hash bindings**, signatures, actual
  two-way sync, strict migration/service shutdown, restart/certificate/data
  retention, preserving uninstall and owned QEMU cleanup pass. Browser stages
  run/stop/restart/stop; production parent records 65 successful HTTP requests.
  Chromium and synthetic CEF are fixtures, not actual Steam CEF or a managed Frame.

Raw audit results, source fingerprints, previous-head observation, connection
log and verifier programs are retained in `framey-deck-shelves-main4558a36-integration-2026-11-01-raw.json.gz`.
Packet SHA-256: `20faea55a611971b889e909eb1705a7db9bfb0b041957208c63d19ddc584aa56` (59127 bytes).

## Claims and remaining gates

Deck Shelves remains **partial**; SteamGridDB remains **broken**. Syncthing's
installer remains disabled. Store 130 remains exactly **1.0.1**. Separate GitHub
v1.0.2 ZIP `12ab420f06023cd13717489aa92a1babd09dec8566a601f4b4bb93464fbc92b6`
remains **unverified** in compatibility lookup. No live-store requery was made.

Require fresh exact publication-head CI/e2e/native AMD64+ARM64/ownership/all
triggered package modes, then current-main CI, required checks, feedback and
mergeability review before merge. Prior-head executions and byte-equivalent
inputs do not qualify new-head execution. No failed/cancelled/skipped required
gate is accepted. No real Frame was contacted, woken or sent input; official UI,
Steam CEF, worn visual/controller behavior and release smoke remain unverified.
No schedule, pre-existing headset data, security setting or PR #113 was touched.
This evidence neither merges nor releases anything. Release remains held until
all exact release-commit, tagged installer, checksum, publisher dry run and locked
real-Frame smoke gates pass.
