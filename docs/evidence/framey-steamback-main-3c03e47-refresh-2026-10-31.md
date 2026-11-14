# Steamback integration with the Deck Settings main update

Verified on 2026-10-31T15:52:29.182970+00:00. PR #527 normally merges main `3c03e478a2fab181e6bdfe60ada6038663843ab3` into prior head `d7b56564459cbaf23e13746f6991c7c8900e7b59`. Tested source: `4b9d5b22a29026683c031d2a2fc0298c6b839c76`. Final evidence-only changes require all 18 source fingerprints to remain identical.

Steamback remains **partial**. This repairs a reproduced child IPC EOF unload failure for exact store 46, version 1.0.0-1, archive `ed5f2fbb47cdfc3aa9a4349a139ab20c29976117a3be0de7e8a588bb265ee7f3`. Existing copies need Update/reinstall. It preserves the original save engine and every other published archive member.

## Fresh verification

- SHA-256-verified published Decky 3.3.0 AMD64 executes repaired/original controls through literal legacy RPC, with 11/9 calls. Private save discovery, backup, restore and undo pass with independent content assertions.
- Repaired controlled-peer-EOF and ordinary restarted stops complete in 0.239/0.214 seconds, with the original `Steamback exiting!` unload hook and no forced kill. The original-source negative retains its forced stop at 5.245 seconds and lacks the hook. The negative is not a compatibility pass.
- Every stop snapshots private runtime and remote trees before and after shutdown. Independently decoded base64, SHA-256 and bytes establish the original backup contains `old`, undo contains `new`, and the final remote save contains `new`. Restarted save information matches. Owned descendants disappear, adopted children exit zero and an unrelated sibling survives.
- Independent installation checks the exact managed backend/helper, every archive member, receipt and removal. The adapter matches source; the save engine beneath the EOF prefix remains the published original.
- Free Loader repaired/original controls make 11/7 RPCs, preserve private settings/cache and stop repaired children cleanly twice. Deck Settings repaired/previous-managed controls make 6/3 RPCs and retain its original unload hook on both repaired stops. Both controls retain expected negative forced stops. Deck Settings rejects self-signed TLS before any HTTP request; real upload is unverified.
- All three native reports carry the same 18 input fingerprints. Source/AST/catalog audits preserve main's other 36 runtime dispatch bodies, other exact installer branches and payload dispatches, other 115 catalog rows, and all 116 compatibility status/install policies. Shared IPC, console, official inventory, Deck Settings and Free Loader fixtures match main.
- Full server suite: 1,951 tests, 16 platform/optional skips, no failures, 253.161 seconds. Website: 18 tests, no skips. Generated docs and diff checks pass.
- Production HTTP/SSH installer method: all 37 pinned fixtures, no skips. Receipts, delivered backend/helper hashes, frontend bytes and removal pass. All owned containers, volumes, networks and image tags are absent afterward, independently checked. This installer method does not execute official backends or replace full e2e.

## Evidence

[Structured audit](framey-steamback-main-3c03e47-refresh-2026-10-31.json) and [raw native reports, private snapshots, logs and auditors](framey-steamback-main-3c03e47-refresh-2026-10-31-raw.json.gz). Raw JSON SHA-256: `bd53c0945323caaff58538a19c84d32ce33d18138081c3e62cb90ff09d3ae606`. Gzip SHA-256: `fd31d387ca94cc7e923192f702d84b7f35fa5527930633ee69fd64168cea7acd`.

The original strict red and earlier ARM64 observation remain [historical evidence](framey-steamback-ipc-eof-2026-10-31.md); neither was rerun in this refresh. Its red failure did not serialize save snapshots; these fresh repaired/original controls do retain snapshots. A historical ARM64 failure's peer history is unknown, so the sole cause is not established.

## Limits and remaining gates

Only the three focused native cases ran locally, on AMD64. Full matrix and full e2e did not run locally. Fresh exact final-head hosted CI/full e2e/native AMD64+ARM64/ownership/PC/every triggered package mode, completed exact current-main CI, mergeability and unresolved feedback remain mandatory. Expected full matrix: 45 probes, 34 positive archive pins, 18 input fingerprints. Scoped shutdown passes do not establish globally clean runtime. Published syntax warnings remain in raw logs.

No automatic game triggers, real Steam saves, browser, actual Steam CEF, managed Frame installation, wearer/controller, tagged installer or release proof. Native process cleanup is independently checked; container/image cleanup is source-bound. Installer resource absence is independently checked. No real Frame, hourly schedule or pre-existing user data was touched. Release remains held until all exact release-commit gates and a separately locked real Frame smoke pass.
