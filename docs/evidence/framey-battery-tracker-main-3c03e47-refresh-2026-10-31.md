# Battery Tracker integration with the Deck Settings main update

Verified 2026-10-31T16:11:37.565991+00:00. PR #519 normally merges exact main `3c03e478a2fab181e6bdfe60ada6038663843ab3` into
prior head `be72d3f94cb0e9aa1f24d05d9eddad55272ec536`. Tested source: `fb731b32c5da68a5dd73db2e4c06a84a6f5e861c`. Subsequent
evidence-only changes retain all 18 native input fingerprints. Existing hosted
jobs are preserved until terminal before pushing. No history is rewritten.

Battery Tracker 0.2.0 can answer RPCs while its child is force-killed and loses
buffered samples. The exact-archive repair lets its existing cancellation and
SQLite flush finish after peer EOF. Compatibility remains **partial**. Existing
installations need Update/reinstall; no real-battery or VR claim follows.

## Fresh verification

- Published digest-verified Decky 3.3.0 AMD64 runs the repaired and previous-managed
  negative cases through 38/36 RPC observations.
  Counts include polling and may vary. Repaired parent-only stops finish in
  0.225/0.225 seconds, with zero forced kills, selected shutdown errors or surviving
  owned process identities. Two adopted children exit zero at each stop and an
  unrelated sibling survives. The prior-managed negative reproduces one forced
  kill at 5.247 seconds and loses pending samples.
- Both final private SQLite snapshots are independently base64-decoded,
  SHA-256 checked, opened read-only, integrity-checked and compared with reported
  rows. Repaired first-stop rows are returned after restart and grow at the
  second flush. The negative database remains empty. No user database is used.
- Installation reconstruction verifies store 67 archive
  `91c388d3c1b52079314045b79671ad55c767510658b6193f6936ed6cad383b94`, both receipt shims and exact helper bytes. The prior
  managed backend beneath only the EOF prefix remains byte-identical. Published
  files outside the existing managed backend/manifest changes are unchanged;
  the unnecessary root request stays removed.
- Independent AST/source comparisons preserve main's other 36 native dispatch
  bodies, other 33 cases, every other installer branch/payload dispatch, existing
  e2e assertions, the other 115 complete catalog rows and all 116 status/install
  policies. Battery Tracker's prior runtime body, private lifecycle helper and
  catalog row remain unchanged. Shared IPC/console/inventory and main's Free
  Loader and Deck Settings fixtures remain unchanged.
- Free Loader repaired/original controls make 11/7 RPCs,
  preserve private settings/deal snapshots and stop repaired children cleanly
  twice. Deck Settings repaired/previous-managed controls make
  6/3 RPCs, run its original unload hook twice for
  the repair and reject self-signed TLS before any HTTP request. Both old-source
  controls retain forced stops. All three reports share 18 input fingerprints.
- Full server suite: 1,949 tests, 16 optional/platform
  skips, no failures, 254.693 seconds. Website: all 18 tests,
  no skips. Generated compatibility docs and whitespace checks pass.
- The production HTTP/SSH installer method passes all 37 pinned store
  transactions without skips, including installed-file/receipt assertions.
  Owned containers, volumes, networks and image tags are removed, and absence
  is independently checked. This method does not execute official backends or
  constitute the full e2e suite.
- Three pre-existing untracked evidence files in the original Battery Tracker
  worktree remain byte-identical. Their stale historical outer gzip hash is
  recorded and excluded from this source's qualification; none is copied or staged.

## Evidence and limits

[Structured audit](framey-battery-tracker-main-3c03e47-refresh-2026-10-31.json) and [raw reports, SQLite snapshots, logs and
verifiers](framey-battery-tracker-main-3c03e47-refresh-2026-10-31-raw.json.gz). Raw JSON SHA-256: `19dd9c2615eb972f3c7e2133d1ed770f04da1c554c0b390c5e1e96eac33dd59a`.
Gzip SHA-256: `8419586d18399899f116f8307d35c036d584492b568462e0d093c50301bb75d0`.

Only three focused native cases ran locally, on AMD64. Full native matrix and
full e2e did not run locally. Expected full matrix: 45 probes, 34 positive archive
pins, 18 source inputs. Generic runtime-console clean qualification stays false;
strict plugin-specific checks establish these stops, without a global clean or
error-free runtime claim. Actual Deck Settings uploads remain unverified.

Fresh exact final-head CI/full e2e/native AMD64+ARM64/ownership/PC/every triggered
package mode, completed exact-current-main CI, feedback and mergeability remain
mandatory. Earlier green runs do not qualify this integration. Syncthing stays
disabled. No refreshed browser, real battery, long-term recording, Steam CEF,
managed Frame, wearer/controller, tagged installer or release proof. No headset,
hourly schedule or pre-existing user data was touched. Release remains held until
all exact release-commit gates and a separately locked real Frame smoke pass.
