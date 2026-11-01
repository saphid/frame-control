# PlayTime integration with Deck Shelves main

Implementation `82b2e3c7f8e8ce5a571644996fdd18e11ecb5945` normally merges prior #511 head
`49e2cc0f17c51553eea5b6c4a524ca63352cc976` and main
`9b2f3c2634a61767ebc52099f595229b2515d96f` without conflicts.
Whole-module AST audits retain the entire main checker, runner, official pin
module, inventory test and generated-doc logic outside the PlayTime additions.
All **1718 other main files**, including production code and existing evidence,
are byte-identical. Only 11 non-evidence files differ for PlayTime tests/fixture
and verification notes; all 34 main native cases, all 116 install/status policies
and the other 115 complete catalog rows are preserved. The unmodified PlayTime
3.2.5 archive remains SHA-256
`10fc3beea48991c77cb02867e919b618d4cd6d5e9c6a6d0ccd5266c13214039f`.

Fresh combined-source verification:

- **105 focused tests, zero skips**, covering installer transactions,
  compatibility, native coverage and bounded package timeout diagnostics.
  Generated compatibility docs pass their check.
- Published Decky 3.3.0 native **AMD64**, in networkless/device-free disposable
  containers: **22 PlayTime RPCs**, all 40 original Python source hashes, six
  SQL readbacks and two independently decoded SQLite snapshots with integrity
  checks. Paused sessions are refused, users remain isolated and state survives
  two parent-only loader stops and restart. Scoped owned identities are reaped;
  full process snapshots and global clean-plugin shutdown remain unverified.
- Deck Shelves: four managed RPCs, two clean parent-only stops and restart,
  original unload hooks, settings/backup bytes and metadata retained, unrelated
  sibling preserved. Three original-backend negative RPCs reproduce one forced
  plugin stop; that negative is not a compatibility pass. Independent audit
  checks persisted bytes, console hashes and owned identities.
- Both reports and independent audits bind the same **28** runtime source
  hashes. An evidence-only follow-up commit does not change these inputs.

The [previous full-suite and simulator evidence](framey-playtime-main3d6145c-integration-2026-11-01.md)
and old-head all-four-package qualification apply to earlier sources, not to a
fresh full execution of this combined source. Final-head hosted full CI, native
AMD64/ARM64, catalog e2e and all triggered package gates remain required, along
with exact current-main green and complete review/mergeability checks. No merge
or release is qualified by this local packet.

Compatibility stays partial. Automatic PlayTime recording, live Steam library,
existing-user database migration, official rendered UI/Steam CEF, managed Frame
and wearer/controller behavior remain unverified. No real hardware, schedules,
security settings, PR #113 or pre-existing user data were touched. Store ID130
stays exactly 1.0.1; separate GitHub1.0.2 is not a store-version claim. Syncthing
installation remains disabled.

[Summary](framey-playtime-main9b2f3c2-integration-2026-11-01.json) and
[raw reports, snapshots, logs and verifiers](framey-playtime-main9b2f3c2-integration-2026-11-01-raw.json.gz).
