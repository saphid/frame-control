# Animation Changer integration with Deck Shelves main

The normal merge of main `9b2f3c2634a61767ebc52099f595229b2515d96f`
into #537 produced implementation source
`d788db3de3582df743fc2f8b8f0571b5f924144f`.
The two adjacent installer conflicts were resolved by retaining both exact
archive-specific deliveries and repairs. Independent source review verified
all added installer lines from both parents. The catalog semantic diff from
main remains only row 23 reason, verification and required shims; all 116
versions, digests, flags, install policies and classifications are unchanged.

Fresh combined-source verification:

- **118 focused tests, zero skips**: installed Animation Changer archive,
  installer transactions, compatibility claims and native coverage inventory.
  Generated compatibility documentation also passes its check.
- Published Decky 3.3.0, networkless/device-free native **AMD64**: Animation
  Changer **23 RPCs**, all three default/apply/repeat/switch/reset paths,
  original bytes/inodes restored. Independent audit binds all **29** runtime
  input hashes and installed backend/helper bytes. Parent-only loader exit zero
  without forced kill; generic clean shutdown remains false and no strict
  Animation Changer restart proof is claimed.
- The same loader/source, Deck Shelves **four managed RPCs**, two clean
  parent-only stops and restart, original unload hooks, settings/backup bytes
  and metadata retained, unrelated sibling preserved. The expected original
  backend negative made three RPCs and reproduced one forced plugin stop.
  The independent audit checks console digests, owned identities, persisted
  bytes and all 29 input hashes. The negative is not a compatibility pass.

The [original full suite/site/simulator record](framey-animation-overrides-2026-11-01.md)
applies to the earlier PR implementation. It is not a fresh full combined-source
run. Final-head hosted CI, both native architectures, full catalog e2e and
package audits remain required before merging. No new release is qualified.

Actual Steam playback, downloads, real-user migrations, rendered controls,
real Frame and wearer/controller behavior remain unverified. No hardware or
pre-existing user files were touched; only disposable native fixtures ran.
Animation Changer remains partial, with the original recovery limits intact.

[Summary](framey-animation-main9b2-integration-2026-11-01.json) and
[raw logs, snapshots and independent verifiers](framey-animation-main9b2-integration-2026-11-01-raw.json.gz).
