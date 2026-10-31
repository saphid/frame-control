# Retain general-native Decky console evidence

Initial retention source: `61b4d7d8ee34bea39643fce10c6b166a1eec6dd6`, based on main `4049722d1f52d06ef76216ef3ea39103e599ff54`.
This changes test infrastructure only. Product/plugin/catalog bytes and archive
pins are unchanged. The follow-up below changes loader cleanup signaling.

## Problem and change

The general native probe previously printed its case JSON before final cleanup.
Its exception handler retained only the last 12 KB of the available console,
also before cleanup. Most native artifacts therefore lacked late shutdown output.

Each completed case now retains the complete available file after cleanup under
`runtimeConsole.text`, with its SHA-256 and every recorded process stop/return
code/forced-kill escalation. Probe and cleanup exceptions print the complete
available console on stderr and emit no successful case JSON. The new helper is
included in the runner's ten source fingerprints. The initial retention change
left cleanup signaling unchanged. Neither that change nor the follow-up below
replaces case-specific assertions or adds a blanket clean-stop gate.
`cleanShutdownVerified` is explicitly false.

## Initial validation and findings

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
Wine Cellar case (ID 68) returns its loader with exit 1 after its RPC assertions.
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

Those failures remain historical evidence. An unchanged-head rerun or a weaker
lifecycle assertion does not qualify them as clean.

## Follow-up: let Decky unload its children

Main `dd12031f55ccbcba01aa07296080495df1935af1` was merged normally before
the follow-up. Frozen source `277bbb1b4b27c613ff03a5510da34993361872bc`
changes the finalizer and eleven restart paths to send SIGTERM only to the
owned Decky loader. The loader can then run its plugin unload protocol without
the fixture simultaneously terminating its children. Auxiliary fixture groups
retain their existing cleanup. The finalizer waits eight seconds, allowing
Decky's own five-second plugin-stop deadline to finish before bounded group
SIGKILL cleanup. Escalation and every return code remain visible in the record.

Each finalizer stop records whether it identified the loader, sent parent-only
SIGTERM or signaled an auxiliary group. A false signal flag can also mean the
process had already exited before the finalizer; it does not describe earlier
case-specific restart operations. Forced group cleanup is separately recorded.

Eight focused tests pass, including a real parent/child fixture whose child
must stay alive until the parent explicitly stops and reaps it. Existing full
output, failure, forced cleanup and no-success-after-exception tests still pass.
This changes test teardown only; it does not repair plugin code or establish
clean shutdown for the full catalog. `cleanShutdownVerified` stays false.

The follow-up full AMD64 replay returned all 38 probe results. Independent
verification checked all 33 exact published archive pins, ten source
fingerprints, all console hashes, all five expected negative controls, Deck
Progress SQLite snapshots and Ludusavi controls. The machine record retains
this separately under `parentOnlyFollowUp`; the initial replay remains intact.
All 57 finalizer-recorded loader stops returned zero. Across all recorded
processes there were 61 zero exits and five auxiliary SIGTERM exits, with no
finalizer SIGKILL escalation. The eight focused tests and owned container/image
cleanup also passed.

Zero loader exits still do not qualify clean plugin shutdown: the complete
consoles retain one plugin forced kill each for Wine Cellar (68) and Shotty (53),
besides the two deliberate original Deck Progress forced kills. They also
retain 11 JSON parse diagnostics. No `Bad file descriptor`, `Error during
shutdown`, `CancelledError` or pending-task marker appeared in this replay.
Wine Cellar's scoped repair is tracked separately in #515; Shotty's unload
remains unqualified. These observations cover this local source revision only,
and `cleanShutdownVerified` remains false for every general-native case.

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
