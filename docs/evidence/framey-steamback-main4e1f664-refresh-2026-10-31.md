# Steamback integration after the Simple Timer merge

PR #527 normally merges main `4e1f664be47b99fcf88c84d1280126c39d6753b4` into prior head
`b0b798c4189a471f1b98b09946120770ad68d47c` at tested source `9fbb0890a9e44bf60ce8281971f7727e9c8b2976`.
Integration source `5e26b5d14a9c7cbbcef0869f5e4f455b4b520df1` performed the normal merge.
A final range check then caught one pre-existing trailing blank line in the
lifecycle helper. Source `9fbb0890a9e44bf60ce8281971f7727e9c8b2976` removes that line; all native fingerprints
and tests in this record belong to this corrected source.

Overlapping native-input lists, original-source negative controls and exact
installer dispatches retain both complete Steamback and Simple Timer branches.
No history was rewritten. Compatibility stays **partial**; existing managed
copies need Update/reinstall. No save-engine behavior is changed by the EOF prefix.

## Fresh local verification

Digest-verified published Decky 3.3.0 AMD64 discovers exact store 46 Steamback
1.0.0-1, archive `ed5f2fbb47cdfc3aa9a4349a139ab20c29976117a3be0de7e8a588bb265ee7f3`.
Repaired/original controls complete **11/9 literal legacy RPCs** for private save
discovery, backup, restore and undo. The repaired controlled-peer-EOF and restarted
ordinary stops complete in **0.214/0.185 seconds**, with the original
`Steamback exiting!` hook, no forced kills, owned identities reaped, two zero
adopted exits and unrelated sibling preserved. The original-source negative
force-stops after **5.224 seconds** without that hook. It is not a
compatibility pass.

Every stop independently snapshots private runtime and remote trees before/after
shutdown. Base64 decoding, SHA-256, parsed RPC values and exact bytes verify that
the original backup contains `old`, undo contains `new`, and final remote save
contains `new`. Restarted save information matches. Independent installation
verifies the delivered helper, exact receipt/removal and every archive entry;
the published save engine is preserved beneath only the EOF prefix.

The merged Simple Timer control completes **31/10/18 RPCs** with persistent
settings and event assertions. Its four repaired stops complete in
**0.185/0.214/0.225/0.185 seconds** with original unload hooks and no forced kill.
The original timer state failures and previous-managed forced stop remain expected
negatives. Both reports match all **20 native source fingerprints**.

Full server suite: **1,952 tests**, **16 platform/optional skips**,
no failures, **254.261 seconds**. Website: **18 tests**, no skips. One isolated
production HTTP/SSH installer method passes all **37 pinned fixtures**, with
exact Steamback/Timer receipt/backend/helper and removal assertions. Owned
containers, volumes, network and image tags were removed and absence independently
checked. This method does not execute every official backend or replace full e2e.

The source/AST audit reconstructs the complete main runtime checker after removing
only Steamback's exact prior additions/restoring its main probe body. Main's
Timer negative is structurally identical to main. It also preserves main's other
36 runtime bodies, other 33 native cases, other 115 complete catalog rows, all
116 status/install policies, other installer/payload/e2e branches, shared adapter
and Timer helpers. The prior Steamback probe/top-level negative are unchanged. Its lifecycle helper
removes only one trailing blank line, with identical AST; all checks below were
rerun on the resulting source. Generated docs and diff checks pass.

## Limits and remaining gates

Earlier hosted/full-native/strict-red results and Free Loader/Deck Settings
native controls remain historical; they were not rerun in this refresh. The
historical strict red did not serialize save snapshots; these fresh controls do.
Historical ARM64 peer history is unknown, so its sole cause is not established.
Published syntax warnings remain in raw logs. Scoped lifecycle results do not
establish globally clean runtime. Full e2e/native matrix did not run locally.
Fresh exact final-head CI/full e2e/native AMD64+ARM64/applicable PC/ownership/
every triggered package mode, completed exact current-main CI, mergeability
and unresolved feedback remain mandatory.

No automatic game triggers, real Steam saves, browser, actual Steam CEF, managed
Frame install, wearer/controller, tagged installer or release proof is claimed.
Headset, hourly schedules and pre-existing user data were untouched. Release
remains held until every exact release-commit gate and locked real Frame smoke.

[Structured audit](framey-steamback-main4e1f664-refresh-2026-10-31.json) and [raw reports, snapshots, logs and verifiers](framey-steamback-main4e1f664-refresh-2026-10-31-raw.json.gz).
