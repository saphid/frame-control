# Retain general-native Decky console evidence

Source: `61b4d7d8ee34bea39643fce10c6b166a1eec6dd6`, based on main `4049722d1f52d06ef76216ef3ea39103e599ff54`.
This changes test infrastructure only. Product/plugin/catalog bytes, archive
pins and the existing process-group cleanup policy are unchanged.

## Problem and change

The general native probe previously printed its case JSON before final cleanup.
Its exception handler retained only the last 12 KB of the available console,
also before cleanup. Most native artifacts therefore lacked late shutdown output.

Each completed case now retains the complete available file after cleanup under
`runtimeConsole.text`, with its SHA-256 and every recorded process stop/return
code/forced-kill escalation. Probe and cleanup exceptions print the complete
available console on stderr and emit no successful case JSON. The new helper is
included in the runner's ten source fingerprints. This does not change how any
process is stopped, replace case-specific assertions or add a blanket clean-stop
gate. `cleanShutdownVerified` is explicitly false.

## Validation and findings

Seven focused tests pass: four evidence tests (three with real child processes)
and three runtime-inventory tests. A 40 KB fixture verifies that beginning and
shutdown-tail output survives. Separate cases cover probe failure, forced cleanup
and a cleanup exception without successful JSON. Compilation, generated
compatibility-doc verification and diff checks pass.

The local native AMD64 replay returned all 38 existing probe results, including
expected negative controls. Independent audit verified all 33 published archive
pins, all ten source fingerprints, all 38 retained console hashes and post-cleanup
metadata. Deck Progress's managed/original controls retain 36 literal RPC results,
four independently decoded SQLite snapshots, zero managed forced plugin kills
and two original forced plugin kills. Ludusavi retains its three literal results,
original missing-dependency failure, bounded discovery and four parent-only
zero-exit stops. Owned runtime containers and the image tag were removed.

**These returned probe results do not qualify clean general-native shutdown.**
The newly retained files contain 25 `Bad file descriptor` occurrences, 11 JSON
parse diagnostics and one `Error during shutdown`/`CancelledError` pair. The
Emuchievements case (ID 68) returns its loader with exit 1 after its RPC assertions.
Across all recorded processes (loaders plus auxiliary fixtures), return codes
are 42 exit-1, 19 exit-0 and five SIGTERM exits. The two `Sending SIGKILL!` records
belong to the deliberate original Deck Progress unload negative. The general
finalizer itself did not escalate to SIGKILL in this replay.

The [machine-readable inventory](framey-native-console-2026-10-31.json) retains
per-case console digests, byte counts, return codes and diagnostic counts. Full
raw reports/consoles are retained locally, bound by the record's report/log
hashes. Hosted artifacts will provide separate exact-head qualification; no
hosted run is claimed by this local record. The cause of each diagnostic is not
established by merely retaining it.

Next: reproduce the affected general-native stop failures, compare parent-only
loader signaling against the existing process-group signal, and add a clean
zero-exit gate with explicit expected-negative handling. Keep the newly visible
failures as evidence; no unchanged-head rerun or weakened lifecycle assertion
qualifies them as clean.

## Reproduce and limits

```sh
PYTHONPATH=tests:ui python3 -m unittest test_framey_native_console test_framey_decky_runtime -v
python3 scripts/framey-test-decky-runtime.py --loader /path/to/published/PluginLoader \
  --output /tmp/native-console.json
```

Final-head hosted CI, e2e, native ARM64 and all triggered package/ownership gates
remain required. A killed or timed-out container can lose output never emitted
to the host; this does not promise a complete timeout-container console. The
successful-case console hash applies to retained text, not proof that every
plugin stopped cleanly. No real Frame, shared simulator, Steam session, wearer
view, physical controller or new browser result is claimed. No compatibility
classification changes and no release is published.
