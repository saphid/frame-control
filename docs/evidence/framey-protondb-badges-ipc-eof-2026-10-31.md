# ProtonDB Badges: private child IPC shutdown repair

Tested runtime source: `dc2fbca5b0d19643bf293132e85864666c112016`, based on main
`3c03e478a2fab181e6bdfe60ada6038663843ab3`. Later evidence-only commits do
not change the 18 native input fingerprints. No real Frame or schedule was touched.

## Failure and scope

The exact ProtonDB Badges 1.3.4 store archive (ID **14**, SHA-256
`90a3453ac02709cad64096e7539fd8141fa56f99ae3441fc24a4990dc9684358`)
previously showed a positive forced stop in the ARM64 artifact from #525 at
`8c084284e56aeb1dccc04dedc6fa24d68ec0317e`, run 41215967440,
artifact 13048231930. Store ID 36 is SteamGridDB; that is a separate plugin/fix.
The earlier ARM64 socket history is unknown. This controlled reproduction does
not establish the cause of that intermittent observation.

A fresh unmodified AMD64 baseline answered nine RPCs with no forced-stop marker.
The controlled replay closes one additional owned Unix peer in a networkless,
read-only container with a disposable tester home. It never disconnects the
loader's original peer. The original backend then times out on its next metadata
RPC and requires Decky's forced stop after 5.274 seconds. Its original unload
completion marker is absent. The negative is a failure reproduction, not a
compatibility pass.

Install the existing child-local EOF adapter only for this exact ID/digest/folder,
after checking published backend SHA-256
`07ae28331b7d1ab55a6303636026dadd7e5523fde84d95c62899fed6e1c133ba`.
The original main.py remains an exact suffix under the adapter prefix. All other
published members, including frontend, settings implementation and license, remain
byte-identical. Changed archives get no pinned repair; a missing payload refuses
the transaction. Old receipts require update/reinstall. Compatibility stays partial.

## Results

- Published Decky 3.3.0, native AMD64 repaired/original matrix: **10/6 successful
  RPCs**. The repair answers after peer EOF in 0.003 seconds. The negative times
  out after 8.010 seconds; failed RPCs are not counted as successful calls.
- Repaired parent-only shutdowns: **0.185/0.214 seconds**, zero forced plugin kills,
  original unload completion twice, no selected shutdown error markers, recorded
  descendant identities gone and two adopted child exits per stop with status 0.
  Restart discovery and false-valued settings survive. The original-source negative
  records one forced kill at **5.274 seconds**. An unrelated sibling survives both.
- Settings snapshots are independently decoded and hashed before/after both stops;
  exact config bytes survive. This does not prove Steam badge rendering or live
  user's settings behavior.
- The shared test stop helper gains only an optional plugin completion marker.
  Free Loader's native default path passes its existing repaired/negative controls:
  **11/7 RPCs**, repaired clean stops, expected original forced-stop negative and
  exact private settings/cache snapshots retained.
- **1952 server tests, 16 optional/platform skips; 18 website tests, no skips**.
  The existing five keyboard tests pass, including all **66** production-handler
  event scenarios. That merged keyboard fix remains #507; no duplicate PR.
- The single HTTP/SSH installer test method passes all **37** pinned store fixtures,
  including the ProtonDB receipt, backend/helper hashes and partial status. This is
  not the full e2e suite. Owned containers, volumes, networks and image tags were
  removed and absence checked independently.
- Independent source audit: all 115 other complete catalog rows, all 116 status
  policies, every other installer byte, all other native case declarations and 31
  other probe bodies are unchanged. Shared adapter and published ZIP are unchanged.
  Eighteen final native fingerprints match the tested source. Generated docs,
  Python syntax and diff checks pass.

## Limits and gates

Local coverage is focused native AMD64. Refreshed full native matrix, ARM64,
exact final-head hosted CI/e2e/package/ownership checks, current-main CI,
mergeability and unresolved feedback remain required. Earlier hosted heads do not
qualify this final head. Most other native probes still do not uniformly gate
clean shutdown; no global clean-runtime claim follows.

There was no refreshed browser, Steam game-page badge, real Frame, worn visual,
physical-controller or release verification. Keep live store ID 130 pinned to
Games Prefix Manager 1.0.1; its separate GitHub 1.0.2 candidate and #526 are
untouched by this fix. No release is qualified by this record.

The [audit JSON](framey-protondb-badges-ipc-eof-2026-10-31.json) and [compressed raw reports/logs/verifiers](framey-protondb-badges-ipc-eof-2026-10-31-raw.json.gz)
retain exact calls, consoles, settings bytes, source hashes and cleanup evidence.
Raw bundle SHA-256: `bdae2a134054a1bd7e04b8b410cc2f72bb4a841dbfefda1c28216864096dcb91`.
