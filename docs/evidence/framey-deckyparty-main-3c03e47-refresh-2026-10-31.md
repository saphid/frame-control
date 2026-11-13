# DeckyParty repair with the Deck Settings main update

PR #518 now includes main `3c03e478a2fab181e6bdfe60ada6038663843ab3` through normal merge
`e0bdbb48abfc0627cb712c3aaba56bbc68b67c9e`, whose other parent is `a11ea0c2ac62d70b5ce6d35c64917a50204d1952`.
The source-inventory and installer dispatch conflicts preserve the merged Deck
Settings repair and DeckyParty's exact-archive child IPC repair. Free Loader
and TabMaster behavior from main also remain present. No history was rewritten.

## Combined-source verification

- Published Decky **3.3.0 native AMD64** runs four scoped pairs: DeckyParty,
  Free Loader, Deck Settings and TabMaster. All **18 source fingerprints** are
  identical across the four reports and match the merge source above.
- DeckyParty's **15 repaired / 8 previous-managed RPCs** retain authenticated
  private listing/download/upload/delete, anonymous/wrong-password refusals,
  disable/restart and unrelated-child survival. Three repaired closed-peer
  reloads take **0.363/0.369/0.367 seconds**, execute the original unload hook, and
  leave no recorded plugin or server identity alive. Its final parent-only
  stop also exits zero and reaps its owned processes.
- The previous-managed source reproduces a forced reload after
  **5.274 seconds**, leaving its recorded server
  alive until the fixture cleans up that exact owned server session. Its fresh
  replacement then stops normally. That final stop does not make the negative
  reload a compatibility pass.
- Free Loader retains **11/7 RPCs**, exact private settings/deal snapshots,
  two repaired clean stops and the forced original-source negative. Deck
  Settings retains **6/3 RPCs**, two repaired clean stops, its original unload
  hook and the forced prior-managed negative. Both Deck Settings controls
  reject a self-signed upload endpoint before any HTTP request.
- TabMaster retains **47/48 RPCs**, valid-backup repair, malformed/non-object
  refusals, private readbacks and restart persistence. Its recorded malformed
  JSON diagnostic remains in the original-source control. The positive case
  requires one forced unload at **5.223 seconds** despite successful RPCs;
  existing #525 owns that shutdown repair. DeckyParty retains offline IP-discovery errors.
  This is not an error-free or globally clean runtime claim.
- Full server suite: **1,949 tests**, **16 platform/optional
  skips**, no failures, **250.491 seconds**. All **18 website
  tests** pass without skips. One isolated HTTP/SSH installer method passes
  **37 pinned fixtures**, no skips, including exact receipts, installed backend
  and helper hashes, and removal. Owned containers, volumes, network and image
  tags were removed and absence independently checked. Generated docs and
  `git diff --check` pass.

## Preservation and installation checks

An AST audit proves main's other **36 runtime bodies**, non-DeckyParty
installer and e2e branches, the other **33 native cases**, other **115 complete
catalog rows**, all **116 status/install policies**, and shared IPC/console/
archive inventory are preserved. DeckyParty's previous helper, contract fixture
and runtime body remain unchanged. Removing only its additional runner input
and negative control reconstructs main's runner exactly.

An independent production installation verifies that the backend differs from
the previous managed repair only by the three EOF import/install lines; all six
other published members are byte-identical. The helper matches the shared
adapter, and the installer test requires both receipt shims. Existing managed
copies need Update/reinstall. Compatibility stays **partial**.

[Structured audit](framey-deckyparty-main-3c03e47-refresh-2026-10-31.json) and
[compressed raw records](framey-deckyparty-main-3c03e47-refresh-2026-10-31-raw.json.gz) retain the four native reports,
complete available consoles, independent source/installation and scoped
lifecycle verifiers, full server/site logs, installer logs and owned cleanup.
A later evidence-only commit must preserve all 18 tested source inputs.

## Remaining gates

The full native matrix and full e2e suite were not run locally in this refresh.
Fresh exact final-head hosted checks/e2e, native AMD64/ARM64, PC/ownership,
every triggered package mode, current main, feedback and mergeability remain
required. Old green heads do not qualify this merged source. Native
container/image cleanup is source-bound to the frozen runner; the installer
has a separate retained Docker-resource absence check. Peer-loader raw
consoles and exit status are not independently retained here.

No new LAN/HTTPS, browser/panel, real Steam CEF, managed Frame,
wearer-visible/controller, tagged installer or release proof is claimed. No
headset or hourly schedule was touched. Release remains held until every exact
release-commit gate and locked real Frame smoke passes.
