# Deck Shelves integration after the Simple Timer merge

PR #528 normally merges main `4e1f664be47b99fcf88c84d1280126c39d6753b4` into prior head `d247458d6bdb8f5aef1a4bb3f4285c5cf40e18cd`
at tested source `3f068191bfb76e202e2fdb772aff88c454c094c2`. Two conflicts retain both Deck Shelves and
Simple Timer installer dispatches and native fingerprints. No history was
rewritten. Compatibility stays **partial**; existing copies need Update/reinstall.

## Fresh local verification

Digest-verified published Decky 3.3.0 AMD64 discovers exact store 135 Deck
Shelves 2.0.0, archive `b566280ad38fd3ecd584b5b46a855f301539eb9a86063834c64b7045f7063f91`. Repaired/original controls
complete **4/3 RPCs**. Repaired parent-only stops take **0.214/0.164 seconds** with
the original unload hooks, zero forced kills, zero selected stop errors and
no remaining recorded owned identities. Adopted child exits are zero and an
unrelated sibling survives. Private settings and backup bytes, hashes, decoded
JSON and mode/uid/gid/inode/mtime metadata remain unchanged across stops and
restart. The original backend requires a forced stop at **5.223 seconds**
without completing its hook. This negative is not a compatibility pass.

Independent installation preserves the exact published backend beneath only
the three-line EOF adapter prefix and every other published archive member.
The shared adapter is byte-identical to main.

Current-main Simple Timer completes **31/10/18 RPCs**, retaining settings,
events, restart state and original/previous-managed negatives. Its four repaired
stops take **0.275/0.196/0.214/0.214 seconds** without forced kills.
Both native reports match all **20 source fingerprints**. Scoped lifecycle
results do not establish globally clean/error-free runtime; generic runtime
console qualification remains false.

Full server suite: **1,953 tests**, **16 platform/optional skips**,
no failures, **257.362 seconds**. Website: **18 tests**, no skips. One isolated
production HTTP/SSH installer method passes all **37 pinned fixtures**, including
Deck Shelves/Timer receipts and delivered backend/helper bytes. Owned containers,
volumes, network and image tags were removed and absence independently checked.
This method does not execute official backends or replace the full e2e suite.

Whole-checker/source/AST/catalog audits preserve main's other 36 runtime bodies,
other 33 native cases, other 115 complete catalog rows, all 116 status/install
policies, every other installer/payload/e2e branch, shared adapter and current
Timer helpers. Deck Shelves' prior runtime body, strict lifecycle helper and
top-level negative remain unchanged. Removing only its scoped additions
reconstructs main's complete checker, runner and installer. Generated docs and
full-range diff checks pass.

## Limits and remaining gates

Earlier strict-red, hosted/full-native, ARM64 and Free Loader/Deck Settings/
TabMaster controls remain historical, not rerun here. #525 owns the prior
TabMaster unload failure; successful backup/restore is not clean-shutdown proof.
Full native matrix and full e2e did not run locally. Fresh exact final-head CI,
full e2e, native AMD64/ARM64, applicable PC, ownership, every triggered package
mode, completed exact current-main CI, feedback and mergeability remain required.
Peer-loader raw consoles/exit status are not independently retained here;
historical peer/socket history is unknown.

No Steam Home injection, new browser/panel, actual Steam CEF, managed Frame,
wearer/controller, tagged installer or release proof is claimed. Headset,
hourly schedules and pre-existing user data were untouched. Release stays held
until all exact release-commit gates and locked real Frame smoke pass.

[Structured audit](framey-deck-shelves-main4e1f664-refresh-2026-10-31.json) and [raw reports, snapshots, logs and verifiers](framey-deck-shelves-main4e1f664-refresh-2026-10-31-raw.json.gz).
