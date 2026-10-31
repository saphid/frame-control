# PlayTime private sessions through published Decky

On 2026-10-31, the exact official **PlayTime 3.2.5** archive (store ID 66,
SHA-256 `10fc3beea48991c77cb02867e919b618d4cd6d5e9c6a6d0ccd5266c13214039f`)
passed private session RPC and persistence checks in published **Decky 3.3.0**
on an isolated local AMD64 container. The original plugin is unmodified; no
production shim or installer behavior changed. Compatibility remains **partial**.

The [machine-readable evidence](framey-playtime-private-sessions-2026-10-31.json)
retains every RPC result, six SQL stage readbacks, both final SQLite snapshots,
the complete loader console and all eight runtime-source fingerprints. Runtime
source is frozen at `b61a7382bebfb8df16eef47347f0b567996eb1f5`.
The loader SHA-256 is
`e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181`.

## What passed

- Actual loader discovery and 22 API1 calls write a synthetic 300-second Alice
  session and 600-second Bob session for the same synthetic app ID. These are
  disposable fixture identities, not real Steam accounts or games.
- A second Alice session is skipped while paused; independent SQL still reads
  exactly 300 seconds. Removing the pause flag succeeds.
- Switching users preserves separate names, totals and session rows. Both
  databases survive complete loader shutdown and restart. Current-user selection
  resets on restart and is set explicitly before the readback.
- Independent verification decodes and hashes both 114,688-byte SQLite snapshots,
  opens them read-only, checks exact game/session/total/tracking rows and requires
  `PRAGMA integrity_check` to return `ok`. All 40 Python backend source hashes
  match the original ZIP, and the probe compares every installed archive member
  byte for byte before using it.
- Two parent-only SIGTERM shutdowns exit zero in about 0.215 seconds each.
  Five owned process identities are absent after each shutdown; the container
  fixture collects two adopted child exits, both zero, without signaling them.
  The retained console contains both completed shutdowns and none of the tested
  shutdown-error, pending-task, canceled-error or bad-file-descriptor markers.
  It does contain Decky's warning about running as an unprivileged user.

## Reproduce

```sh
python3 scripts/framey-test-decky-runtime.py --loader /path/to/published/PluginLoader \
  --case 66 --output /tmp/playtime-private-sessions.json
```

The normal native AMD64/ARM64 CI matrix includes this case. Only the local AMD64
run is qualified by this document; new PR CI and ARM64 results are pending.
For compact publication, the two original snapshot `base64` fields are encoded
as deterministic `gzipBase64` with gzip `mtime=0`. Decompress before checking
the unchanged SQLite SHA-256 or opening the database. All other runtime fields
are retained. The JSON records hashes of the original report and runner log.

## Failures and cleanup

Two earlier fixture attempts failed and are retained locally with hashes in the
JSON: the first did not collect adopted exited descendants; the second incorrectly
required no SQLite WAL file after otherwise successful RPC/restart checks. The
final probe closes observers explicitly and serializes a complete committed
snapshot through a read-only connection. Neither failed attempt qualifies as
a successful runtime check.

The canonical runner removed its owned runtime resources. Independent Docker
inspection found the successful image ID and all ancestor containers absent.
The final live container configuration was not captured; an earlier attempt's
captured configuration is not presented as final-run evidence. No real Frame,
shared simulator, pre-existing user data or active Steam session was contacted
or changed.

## Refresh against current main

Main `4049722d1f52d06ef76216ef3ea39103e599ff54` is merged normally,
without rewriting branch history. Six additive conflicts retain PlayTime,
Ludusavi dependency discovery, Deck Progress and its unchanged-original unload
negative control. All 116 catalog versions, digests, classifications and install
policies match main; only PlayTime's explanation/evidence metadata differs.
The keyboard handlers, server, IPC adapter and production plugin store code
match that main byte for byte.

The merged source passes 87 focused host tests. Targeted local native AMD64
checks independently verify PlayTime's 22 literal RPC results, 40 original Python
hashes, six SQL readbacks, two read-only SQLite snapshots and two clean parent-only
loader stops. They also retain Deck Progress's 36 RPCs, four decoded SQLite
snapshots, zero managed forced kills and two expected original forced kills,
plus Ludusavi's three literal dependency results, original missing-dependency
failure and four parent-only zero-exit stops. All ten runtime source fingerprints
per report match the merged source; owned containers and image tags are removed.
The resulting full native matrix contains 39 probes and 34 published archive
pins; these targeted local checks do not qualify that entire matrix.

Historical hosted qualification at `74eb426` remains scoped to that head.
Fresh final-head hosted CI, e2e, AMD64/ARM64 native, ownership and all triggered
package modes remain required, along with current-main, feedback and mergeability
gates. The keyboard event regression also passes its five tests on this source;
that remains device-boundary test-double evidence. No real Frame, live Steam
session, automatic recorder, new browser or physical-controller proof is added.

## Limits

This probes explicit backend RPC with synthetic timestamps. Automatic recording
still depends on an unsupported private MobX running-app observer. No new browser
render, live Steam library, existing database migration, game lifecycle hook,
ARM64 backend, real Frame, worn view or physical-controller result is claimed.
Earlier frontend evidence and its limits remain separate. All 116 catalog
versions/digests/install policies are unchanged; only PlayTime's evidence scope
and reason are expanded.
