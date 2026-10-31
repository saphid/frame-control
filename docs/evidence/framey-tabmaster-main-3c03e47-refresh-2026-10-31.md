# TabMaster unload repair with the Deck Settings main update

PR #525 normally merges main `3c03e478a2fab181e6bdfe60ada6038663843ab3` at source
`3e1b595422c9f22394bcd9c88f76c79f8146eeb8`, retaining the exact TabMaster 2.15.1 JSON-restore
and child-IPC repairs. The other parent is `e513671e432d1dc300486a9809b1e2f3220117a3`.
Source `f8e70df56d30063c09c19a71d622b90135c014c6` then adds only two e2e assertion lines requiring
that the delivered child IPC helper matches its local source hash. No history
was rewritten. All **18 native input fingerprints** remain unchanged.

## Failure and repair evidence

The preceding local main-derived control used source
`e0bdbb48abfc0627cb712c3aaba56bbc68b67c9e`. Independent AST/fixture
and backend checks prove that its scoped TabMaster runtime and installer
match main `3c03e478a2fab181e6bdfe60ada6038663843ab3`. It completed **47 RPCs** and valid backup/restore,
yet its first stop force-killed the child after **5.223 seconds**. The second
stop exited normally. The raw console hash and original process observations
are retained. Loader exit zero and successful settings calls did not prove
clean plugin shutdown. This is the existing defect owned by #525.

The refreshed published Decky **3.3.0 native AMD64** cases run:

- Repaired backend: **47 RPCs**, private user isolation, shared-tab filtering,
  false values, valid backup/restore and malformed/non-object refusals. Controlled
  peer disconnect and ordinary restarted stops take **0.214/0.214 seconds**,
  run the original unload hook, preserve restart state, reap recorded identities
  with zero adopted exits and leave an unrelated sibling alive. No forced kill.
- Original published backend: **48 RPCs**, retaining the valid-backup restore
  refusal as a negative control. Its two ordinary stops are clean; this does not
  make its restore behavior a compatibility pass.
- Previous managed JSON-repaired backend: **47 RPCs**, preserving valid restore
  while reproducing a **5.223-second forced stop** after controlled peer EOF.
  The fresh replacement stops normally. The failed first unload remains an
  expected negative, not a compatibility pass.

Free Loader **11/7 RPCs** retain exact private settings/deal snapshots, two
repaired clean stops and the forced original-source negative. Deck Settings
**6/3 RPCs** retain two repaired clean stops, original unload hooks, the forced
prior-managed negative and self-signed TLS rejection before any HTTP request.
All three reports have the same 18 source fingerprints, published loader digest
and native architecture. Unattributed JSON diagnostics remain in the repaired
and original TabMaster consoles; no globally clean/error-free runtime is claimed.

## Tests and source preservation

The full server suite reports **1,948 tests**, **16
platform/optional skips**, no failures, in **250.248 seconds.
All **18 website tests** pass without skips. After adding the helper-hash
assertion, one new isolated HTTP/SSH installer run passes all **37 pinned
fixtures**, no skips. It requires TabMaster's exact receipt, backend and helper
bytes and removal. Owned containers, volumes, network and image tags were
removed and absence independently checked. Generated docs and diff checks pass.

The source audit preserves main's other **36 runtime bodies**, other **33 native
cases**, other **115 complete catalog rows**, all **116 status/install policies**,
non-TabMaster installer/e2e branches, shared IPC and main's Free Loader/Deck
Settings fixtures. TabMaster's original strict lifecycle helper is unchanged.
Independent installation proves that the backend is exactly the EOF prefix
plus the preceding JSON repair; every other published archive member is
unchanged. Compatibility stays **partial**; existing copies need Update/reinstall.

[Structured audit](framey-tabmaster-main-3c03e47-refresh-2026-10-31.json) and
[compressed raw evidence](framey-tabmaster-main-3c03e47-refresh-2026-10-31-raw.json.gz) retain current native reports,
complete available consoles/hashes, the main-derived failure and source-equivalence
verifier, installation reconstruction, test logs, helper assertion provenance
and owned installer cleanup. The original strict-red fixture remains historical
and was not rerun here; the current previous-managed negative is fresh.

## Remaining gates

The prior remote head's last package job was preserved during local preparation.
Fresh final pushed-head hosted checks/full e2e/native AMD64+ARM64/PC/ownership/
every triggered package mode, exact current-main CI, feedback and mergeability
remain required. The full native matrix and full e2e suite were not run locally.
Other plugin probes do not uniformly enforce clean shutdown; separate existing
repairs remain queued. Native Docker cleanup is source-bound to the frozen
runner, with explicit process checks in the reports.

No browser/backend integration, library-tab editing, real Steam CEF, managed
Frame, wearer/controller, tagged installer or release proof is claimed. No
headset, hourly schedule or pre-existing user data was accessed. Release stays
held until every exact release-commit gate and locked real Frame smoke passes.
