# Terminal candidate through production HTTP and events, 2026-10-30

The isolated AMD64 replay at `6f6bf63a6d8d722e7770cb15357ba2d99b6452c8`
passed the production parent, panel, local SSH wrapper, METHOD_SCRIPT and
framey-events.js against actual Decky 3.3.0 and the private Terminal candidate
from #490. It also integrates #488's event-name handling. Production UI sources
are unchanged from that combined input snapshot; this adds test fixtures only.

The [independent audit](framey-terminal-production-http-2026-10-30.json)
matched all 161 committed source fingerprints, loader/archive/frontend pins,
private dependency ABI, and the complete 1,582,397-byte checksummed virtio
packet. The real owned Decky user service handled 14 production method HTTP
requests and six event requests. Four native output events traversed the
production event bridge. The DOM driver waits for real subscription/buffer
replies before pasting its fixed private command, then requires an exact
returned output row, excluding command echo, before capture.

All three captures were inspected: [terminal](framey-terminal-http-terminal-2026-10-30.png),
[output](framey-terminal-http-output-2026-10-30.png), and
[removed](framey-terminal-http-removed-2026-10-30.png). Output visibly includes
`18 125`, `framey-browser-output`, and a shell prompt. The created shell's
ancestry reaches the actual owned Decky service; removal reaps that PID.
Closing the production panel removes its event session and listener. Browser,
HTTP server, service, user manager and QEMU cleanup passed; the original dummy
unit was restored and the synthetic release receipt/owned bundle removed.
All renderer observations retained seccomp and no-new-privileges sandboxing.
The 32 existing shared HTTP gateway regressions, syntax and diff checks pass.

Earlier evidence is preserved honestly: the [first driver failure](framey-terminal-http-driver-failure-2026-10-30.json)
advanced before subscription and made no input RPC; the [second transport pass](framey-terminal-http-before-paint-2026-10-30.json)
proved native/HTTP output but captured only command echo before the returned
lines painted. Neither supplies the final returned-output pixel proof above.

This is a networkless disposable desktop VM with a synthetic CEF RPC/event
facade and synthetic managed release receipt. It is not proof of actual Steam
CEF, production adapter/managed installation, ARM64 browser operation, Frame
display pixels or physical controllers. Native AMD64/ARM64 candidate evidence
in #490 is separate. The original published Terminal negative-import test and
managed inventory remain unchanged. No real Frame or schedule was contacted.

The host runner requires a cached browser rootfs, digest-pinned AMD64 loader,
a fresh owned output directory and committed sources:

```sh
python3 scripts/framey-test-terminal-browser.py --production-http \
  --rootfs-tar /path/to/browser-rootfs.tar --loader /path/to/PluginLoader \
  --output /tmp/new-owned-terminal-evidence
```

The default runner mode retains the earlier private-bridge experiment, with
its separate [scope and evidence](framey-terminal-integrated-browser-2026-10-30.md).

## Reproducible CI follow-up

The Decky workflow now includes a `terminal-browser` matrix for native AMD64
and ARM64 workers. Each job checks out the exact PR head, builds a matching
disposable Chromium/systemd rootfs, downloads the digest-pinned native loader,
and runs `--production-http` in matching QEMU TCG without a network NIC or host
bus/home. The runner binds the workflow, rootfs recipe and selected dependency
sources to the committed input snapshot, refuses a guest/loader architecture
mismatch, and saves the complete result packet and three standalone captures.

This CI wiring is a new gate, not a claim that its ARM64 browser run passed.
The earlier AMD64 evidence above retains its exact tested source revision.
Both native CI artifacts must be reviewed separately; compatibility and worn
Frame/controller limits remain unchanged. The stacked branch also includes
#491's read-only migration cleanup repair so package CI uses that same fix.
