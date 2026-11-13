# Deck Shelves 2.0.0: unload after a private IPC peer closes

The exact published Deck Shelves backend can save its private settings but
require Decky to force-kill its child after an IPC peer closes. This repair
lets the original unload hook run. Compatibility remains **partial**; existing
managed copies need Update/reinstall.

## Exact sources and discovery

- Base main: `dd41aede875d7a6b7abac68520784824b96103e9`.
- Strict failing test, with the production installer unchanged from main:
  `60f69f8d18b5c689e4e546b87d988fc05de36acd`.
- Tested repair: `cb3e5af410f7e52d0a5f5f7243d1771a4dd0fd78`.
  The subsequent evidence commit changes no runtime inputs.
- Store 135, Deck Shelves 2.0.0, folder `Deck-Shelves`, API 1.
- Published archive SHA-256:
  `b566280ad38fd3ecd584b5b46a855f301539eb9a86063834c64b7045f7063f91`.
- Published backend SHA-256:
  `f44495405452962de15cd3cdebd0b15b804de31cd5bb261b4bd6938191d06c5c`.
- Repaired backend SHA-256:
  `a8b4cf75ebe369cb738ae2a5babf1981d1c077b5edd59661c216cc145f8c4fd8`.
- Unchanged shared IPC adapter SHA-256:
  `43ad5a8e19270347e6efaeb59ea94f06f149b525ac928e27298325c0b30500e8`.

The original observation came from [PR #525's historical ARM64 job](https://github.com/saphid/frame-control/actions/runs/41203828163/job/124544771154)
at head `5817bc9573845627bbfbdba2af033b2deecabcab`. Artifact 13044442761
has ZIP SHA-256 `402d6eabc5f3bea7f1730ca6696f8fe50f9a34f454e9ba7449e36cd48468b8f9`.
The earlier audit verified the exact successful job, checkout, GitHub artifact
digest, 16 source fingerprints, 34 archive pins and 43 probes. Its Deck Shelves
console retained a forced first stop and an ordinary second stop. This is
historical discovery evidence, not qualification of this repair. The exact
historical socket sequence was not captured.

## Repair and regression test

Only the exact archive/folder/backend receives `deck-shelves-ipc-eof`. The
installer copies the existing IPC adapter into the plugin's `py_modules` and
prepends its three-line installation call. The published backend follows
unchanged. An independent install reconstruction verifies every other archive
file byte-for-byte. Changed archives receive no pinned repair; missing adapter
payloads refuse installation.

The network-isolated AMD64 fixture uses the published Decky 3.3.0 loader, SHA-256
`e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181`.
It discovers the plugin, reads defaults, saves one private shelf, reads it back,
then closes the sole owned Unix peer before signaling **only the loader**.
It does not signal the plugin child or process group to manufacture a clean
stop. An unrelated sibling must survive.

| Source | RPCs | Stop seconds | Forced kills | Original unload hook |
| --- | ---: | --- | ---: | --- |
| Unmodified-main strict test | Fails at first stop | 5.224 | 1 | Absent |
| Repaired backend | 4 | 0.214 / 0.164 | 0 | Both stops |
| Restored published backend, expected negative | 3 | 5.224 | 1 | Absent |

Both repaired stops require loader exit 0, no shutdown diagnostics selected by
the strict helper, no surviving owned PID/start identities, successful adopted
child exits, the original `Deck Shelves backend unloaded` hook, and framework
unload completion. The second stop follows actual loader restart, rediscovery
and a fourth RPC that returns the saved shelf unchanged.

The test retains `settings.json` and `settings.json.bak` as base64, SHA-256,
parsed JSON and mode/uid/gid/inode/mtime metadata. Independent decoding verifies
both files survive stops and restart unchanged. The backup retains the prior
empty shelf list. The restored-source negative is explicitly **not** a
compatibility pass. Generic `runtimeConsole.cleanShutdownVerified` remains false
by design; the plugin-specific lifecycle checks establish the repaired stops.

## Validation and limits

- Full server suite: 1,950 tests, 16 platform/optional skips, no failures.
- Focused installer suite: 67 tests, no skips.
- Website: 18 tests, no skips.
- Production HTTP/SSH installer method: all 37 pinned panel/legacy transactions
  passed, including exact receipt/backend/helper assertions for Deck Shelves.
  This fixture installs/removes official archives without executing their
  backends. Owned containers, volumes, networks and image tags were removed and
  their absence checked independently. This is not the full e2e suite.
- Source audit: the other 36 runtime dispatch bodies, 33 native cases, all prior
  installer branches and payload dispatches, all existing e2e assertions, the
  other 115 full catalog rows and all 116 status/install policies are preserved.
- Generated compatibility docs and whitespace checks pass. All 17 native source
  fingerprints bind the focused run to the tested repair. Hosted full native
  matrix now expects 44 probes, 34 archive pins and 17 source fingerprints.

The [audit JSON](framey-deck-shelves-ipc-eof-2026-10-31.json) and
[compressed raw records](framey-deck-shelves-ipc-eof-2026-10-31-raw.json.gz)
include the failing test, positive/negative native reports, console text,
private-file snapshots, provenance, full test logs and independent verifier
sources. The JSON records the compressed and decoded raw hashes.

No real Frame was contacted. Steam Home injection, actual Steam CEF, ARM64
qualification of this repair, wearer-visible UI and physical controllers remain
unverified. Exact final-head hosted CI/e2e/native/package gates, current main,
feedback, mergeability and integration checks remain required. This evidence
qualifies neither a merge nor a release.
