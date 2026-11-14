# Sample browser settings with actual Decky, 14 November 2026

The unchanged shipped sample UI now passes a Linux AMD64 browser replay against
published Decky 3.3.0 in a networkless native container. The real opaque Framey
host uses a synthetic private parent and receipt; the parent forwards actual
API2 calls over stdin to the container. Frame's production HTTP/SSH parent is
not exercised.

Exact clean source `63f8d3074fbff87e66d4bffcfc8b6352481db19b` passes seven UI stages: initial off,
save on, reopen on, restart/reopen on, Reset confirmation to off, reopen off,
and a second restart/reopen off. An independent audit matches all 27 input hashes,
the deterministic sample ZIP, seven browser/native RPC records, three saved-state
hashes with 0600 modes, three recorded clean parent-only stops and their four
console hashes. There are no recorded remaining descendants or forced fixture
cleanup. The unrelated sibling survives each stop; the browser group and HTTP
server stop. All 19 focused sample and bridge-protocol/failure checks pass on
Linux. The five native-pipe tests skip on other platforms.

All seven final captures match the exact bytes of the inspected preceding run.
The checked toggle and on/off readback survive frontend recreation and loader
restarts. Toasts make the page taller and require vertical scrolling; this is
not a VR usability result. Representative post-restart captures are attached.

The raw report preserves two development harness failures: a legacy envelope
was initially returned to an API2 caller, then same-URL iframe assignment did
not recreate its frontend. Both were corrected in the test bridge. A later audit
also removed the native-only probe's inherited malformed-schema coverage flag,
because this browser replay does not execute those cases. The final report
makes no such claim. Production sample, host and installer bytes are unchanged.

Fresh exact-head hosted CI must pass before merge. ARM64 browser behavior,
physical Frame, worn visibility, controllers, scrolling and VR keyboard remain
unverified. The parent bridge, ownership receipt and DOM input are synthetic.
