# Battery Tracker: integrate Free Loader main without losing pending samples

PR #519's older head `0e079e9c99eef76d158f7f44b67939f9695a1966` had
successful checks but conflicted with main. This refresh normally merges main
`dd41aede875d7a6b7abac68520784824b96103e9` into it. No history is rewritten.
Tested merge source: `274b29832d19b656a5826c445f69d8c300533380`; subsequent
evidence-only commits do not change its 17 native inputs.

The conflict resolution keeps both plugins' adapter dispatch, native helper
fingerprints and old-receipt tests. Independent AST/source comparisons verify
main's other 36 runtime dispatch bodies, 33 native cases, every other installer
branch, all prior e2e assertions, the other 115 complete catalog rows and all
116 status/install policies. Battery Tracker's prior runtime body, private
lifecycle helper and catalog row remain unchanged. The runner gains only the
Battery Tracker fingerprint and negative control relative to main. Main's
Free Loader adapter/helper/fixture and the shared IPC code remain unchanged.

## Fresh isolated native proof

Both focused runs use the published Decky 3.3.0 AMD64 loader, SHA-256
`e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181`,
in network-isolated disposable containers. All 17 recorded source hashes match
the tested merge. These runs do not access a real Frame.

| Case | RPCs | Stop seconds | Forced kills | Result |
| --- | ---: | --- | ---: | --- |
| Repaired Battery Tracker | 37 | 0.215 / 0.215 | 0 | Pending samples flushed; restart persistence |
| Previous managed Battery Tracker | 36 | 5.194 | 1 | Pending samples lost; expected negative |
| Repaired Free Loader | 11 | 0.214 / 0.185 | 0 | Settings/deal persistence; restart |
| Published Free Loader | 7 | 5.225 | 1 | Original unload failure; expected negative |

Battery RPC counts include polling observations and are not a fixed API-call
contract. The first repaired stop changes the private SQLite database from
zero to two rows. Restart returns those samples, and the second stop changes
two rows to three. Each stop signals only the owned loader, reaps its recorded
PID/start identities and two adopted children with exit 0, and preserves an
unrelated sibling. The prior managed backend still needs a forced kill and
leaves the database empty. Both final database snapshots are decoded,
SHA-256 checked, opened read-only, integrity-checked and compared with the
reported rows independently.

An install reconstruction verifies store 67's exact archive SHA-256
`91c388d3c1b52079314045b79671ad55c767510658b6193f6936ed6cad383b94`,
managed backend `ba50a1bc9b81547d718ff155cd6ca0bc37426ba0e9a76a68ccee437abf6a8549`,
prior backend `490d8334b173f956f286e50c9d01af5b83416e8e0037685366efb75c6c323241`,
both receipt shim names and adapter
`43ad5a8e19270347e6efaeb59ea94f06f149b525ac928e27298325c0b30500e8`.
Published files outside the managed backend/manifest changes remain identical;
the manifest still removes the unnecessary root request. The prior managed
backend beneath the adapter prefix is byte-identical.

Free Loader's private settings and deal database are independently decoded,
hashed and checked across both stops and restart. Its original-backend failure
control remains an expected negative. Generic runtime-console clean-shutdown
qualification remains false by design; the strict plugin-specific checks
provide these shutdown results. There is no global clean/error-free runtime
claim for the full catalog.

## Regression checks and preserved work

The full server suite completes 1,947 tests with 16 platform/optional skips.
All 18 website tests pass without skips. The production HTTP/SSH installer
method passes all 37 pinned panel/legacy transactions, including the Battery
Tracker and Free Loader receipts and installed-file assertions. Owned installer
containers, volumes, networks and image tags are removed; absence is checked
independently. This method does not execute official backends and is not the
full e2e suite. Generated compatibility docs and whitespace checks pass.

The original worktree's three untracked exact-head native evidence files are
preserved byte-for-byte. Their historical JSON records a stale outer gzip hash
after an ownership append. They are neither changed nor used to qualify the
new source. The new audit records their observed hashes and this limit; no
unreviewed files from the original worktree are staged.

[Structured audit](framey-battery-tracker-main-dd41aed-refresh-2026-10-31.json)
and [compressed raw records/verifiers](framey-battery-tracker-main-dd41aed-refresh-2026-10-31-raw.json.gz)
retain fresh native reports, database snapshots, complete available console
text, test logs, installer execution/cleanup, source-preservation assertions
and independent verifier sources. The JSON records hashes of the compressed
and decoded raw evidence.

## Remaining qualification

Compatibility stays **partial**. Older exact-head AMD64/ARM64 results do not
qualify this new integration. Fresh final-head hosted CI/e2e, native AMD64 and
ARM64, ownership, PC, every triggered package mode, exact-current-main checks,
feedback and mergeability remain gates. The full native matrix now expects
44 probes, 34 positive archive pins and 17 source fingerprints.

No new browser, real battery, long-term recording, Steam CEF, real Frame,
wearer-visible UI or physical-controller proof is claimed. The headset and
hourly schedules are untouched. No merge or release is qualified by this
local refresh.
