# Free Loader repair with current main — 2026-10-31

Source `7bf8d070e90bcbdc15bdfaa25ed8bf75da63a4ca` normally merges main
`1ac29413186fb29d5844ee9ad1c5c6fd36eeac27` into #522. The sole conflict
was between the Free Loader IPC repair and main's TabMaster restore repair;
both are retained. An AST audit verifies main's other 36 runtime branches
and the prior Free Loader branch. Main's installer code, the shared IPC helper,
the other 115 catalog rows and all 116 status/install policies are preserved.

## Local integration checks

- 90 focused installer, compatibility, runtime-coverage and IPC unit tests pass.
  Generated compatibility docs and `git diff --check` pass.
- Published Decky 3.3.0 AMD64 runs both repaired and original-source Free Loader
  cases. The 11 repaired and seven negative RPCs, exact settings/cache hashes,
  hidden-state persistence and independent installer transaction are audited.
  Both repaired parent-only stops take 0.214 seconds with no forced plugin kill.
  The original source reproduces a forced stop after 5.224 seconds.
- The conflicting TabMaster repair is also exercised in published Decky:
  47 repaired and 48 original-source RPCs match the retained expected sequence.
  Private backup/restore, malformed/non-object refusals and four zero-exit
  owned loader stops pass. Each case retains one JSON diagnostic of unproven
  cause; no error-free console claim follows.
- All 16 runtime fingerprints match the frozen source for both native replays.
  Descendant cleanup is checked with PID/start-time assertions; native Docker
  cleanup is runner/source-bound, without a complete retained Docker inventory.
- One isolated Fake Frame HTTP/SSH installer test passes in 73.057 seconds
  across 37 pinned archives, with zero skips. It verifies the exact Free Loader
  receipt, installed backend/helper and removal, including the current-main
  adapters. Setup/test/cleanup take 128.448 seconds. All owned Compose
  containers, volumes, network and image tags are removed and absence checked.
  This is an installer test, not backend execution, full e2e or a 116-plugin audit.

## Historical ARM64 result

Before integration, exact head `f0d2b7541973edd52ad299aadf090a8326d42fb8`
passed ARM64 [job 124521567308](https://github.com/saphid/frame-control/actions/runs/41195794653/job/124521567308).
Artifact `13042415195` has GitHub ZIP SHA-256
`87040934c6c18dbd3b01d392f859f665a70910c5cc42e1f69e99fbc79e253c8f`.
Exact checkout, all successful job steps, 42 probes, 34 archive pins,
16 source fingerprints and all 42 complete available console hashes are audited.
Free Loader's two repaired stops take 0.214/0.216 seconds; original source needs
a forced stop after 5.205 seconds. Settings/cache readbacks and owned descendant
cleanup pass. Other plugin probes retain forced kills. This individual job does
not establish whole-workflow success or qualify the new integration SHA.

Fresh final-head hosted checks/e2e, native AMD64/ARM64, PC and all triggered
package modes remain required. Compatibility stays partial; existing installs
need Update/reinstall. No live feed, notifications, Steam store, browser,
managed Frame, wearer/controller or release proof was added. No headset or
hourly schedule was accessed. Merge and release remain unqualified.

[Structured audit](framey-free-loader-main-refresh-2026-10-31.json) and
[complete local/hosted reports, logs and verification source](framey-free-loader-main-refresh-2026-10-31-raw.json.gz).
