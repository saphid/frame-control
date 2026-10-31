# Free Loader: private cache persistence and IPC shutdown

Free Loader 1.6.0 remains **partial**. Main's earlier ARM64 native console
showed a forced kill after restart even though settings RPCs passed. A local
AMD64 regression reproduced that result with unchanged production installation
code: explicitly disconnecting the private Unix peer led to a forced kill after
5.224 seconds.

The repair applies only to archive SHA-256
`05208aee6f6ba824391d8ddc81b1168b2599a9711e7528cdaa789f6cc710b42a`
and the pinned original backend. It prepends the existing child-local IPC EOF
adapter; the published backend, unload hook, settings, cache and feed logic are
otherwise unchanged. All 19 ZIP members, including identical duplicates, were
checked. The manifest, frontend, license and other published bytes are retained.
Old managed installations need update or reinstall. Missing helper payload
refuses an incomplete installation; another archive digest gets no repair.

At source revision `d8bcc077316e23bfc0bbf5bc41dd84040a42ebb8`:

- 96 focused tests passed, including exact installation bytes, guarded removal,
  missing-payload refusal and receipt upgrade reporting.
- An isolated, network-denied AMD64 published Decky 3.3.0 fixture made 11 real
  positive API1 RPCs. Discovery reported frontend `load_type: 1`.
- Private settings and a nonempty synthetic deals cache, including a toggled
  hidden flag, survived restart. Exact settings/cache bytes survived both stops.
- Two parent-only stops completed in 0.196 and 0.214 seconds without forced
  plugin kills. Recorded PID/start-time descendants were reaped, adopted child
  exits were zero, and an unrelated sibling survived.
- Restoring the original backend in the same fixture made seven RPCs and
  reproduced the 5.224-second forced stop. This expected negative does not
  qualify as a compatibility pass.
- Both retained raw consoles had zero JSON-decode diagnostics. This observation
  is scoped to these runs and does not establish global clean plugin shutdown.

The audit verified all 16 tested source fingerprints, preserved all 116 catalog
status/install policies, the other 115 complete rows, the other 33 native cases
and 36 other probe/setup bodies. The complete native matrix now expects
42 probes, 34 pinned archives and 16 source fingerprints; that matrix was not
run locally for this fix.

Fresh final-head hosted checks/e2e, native AMD64/ARM64, PC checks and every
triggered package mode remain required before merge. No feed, notification,
browser, Steam store, managed Frame, wearer or physical controller test ran.
No headset was contacted. Release qualification remains absent.

The [audited record](framey-free-loader-ipc-eof-2026-10-31.json) retains hashes,
stop observations and private file readbacks. The
[compressed raw evidence](framey-free-loader-ipc-eof-2026-10-31-raw.json.gz)
retains the native report, original-production regression log, unit log and
installed-source audit. RPC methods/results are literal; arguments and complete
process-identity assertions remain bound to the retained source hashes.
