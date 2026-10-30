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

The updated runner was replayed locally at
`879ac33981ae2202313284873f6910709bd1f422` on AMD64. Its
[independent audit](framey-terminal-native-ci-local-2026-10-30.json) matched all
164 committed fingerprints, including the CI workflow and rootfs recipe,
and the complete 1,583,753-byte packet with SHA-256
`a8f11520453734ef29a9fd6a77e494ff1b668a875fe378d4081bf7252396d3af`.
The host's packet metadata matched the independent checksum. Four native
output events traversed 14 method requests and six event requests; the exact
returned DOM rows include `18 125`, `framey-browser-output`, and the prompt.
The [terminal](framey-terminal-native-ci-terminal-2026-10-30.png),
[output](framey-terminal-native-ci-output-2026-10-30.png), and
[removed](framey-terminal-native-ci-removed-2026-10-30.png) captures were all
inspected. Shell ancestry/reaping, renderer sandboxing, event listener/session
closure and complete owned cleanup passed again. This validates the updated
local AMD64 runner; native CI and ARM64 browser evidence remain pending.


## Native CI results and retained ARM64 failure

At `391095ba02ee6d4b9a2e9eb39580503e723d9b0c`, the
[AMD64 CI artifact audit](framey-terminal-native-ci-amd-2026-10-30.json)
independently passed all 164 source fingerprints, the complete checksummed
packet, 14 production method requests, six event polls, four native/delivered
output events, and shell/event-listener cleanup. All three captures were
inspected: returned output includes `18 125` and `framey-browser-output`,
then removal leaves an empty active-terminal list. These captures remain in
[artifact 13001366029](https://github.com/saphid/frame-control/actions/runs/41103940032/artifacts/13001366029).
The old fixture's inactive-service flag alone does not establish a graceful
Decky stop.

The [ARM64 failure audit](framey-terminal-native-ci-arm-failure-2026-10-30.json)
matched all 164 source fingerprints and the complete 258,896-byte packet from
[artifact 12999809974](https://github.com/saphid/frame-control/actions/runs/41103940032/artifacts/12999809974).
Backend discovery succeeded, but the unchanged production installed-plugin
list remained unpopulated for the 90-second readiness budget. No Terminal
panel request or browser stage completed. The old packet lacks the installed
status error and request timing needed to explain this; no timeout cause is
established and the failed gate remains failed.

The fixture now retains bounded installed-status HTTP timings/statuses, the
actual production UI error, and the existing passive SSH/process observer's
diagnostics. Production commands, timeouts, replies and exceptions pass
through unchanged, with no cache, retry, serialization or receipt bypass.
The observer is restored during cleanup. No production UI or compatibility
claim is changed to make this test pass.

The branch also incorporates #491's managed Decky `KillMode=mixed` policy.
The owned Terminal unit now uses that policy and the shared bounded stop
observer, requiring inactive state, `Result=success`, zero exit status/MainPID
and the original PID gone. A stop failure is retained and remains fatal;
the fixture no longer treats any inactive unit as sufficient shutdown proof.
The updated [local AMD64 replay audit](framey-terminal-status-trace-local-2026-10-30.json)
at `19c351fd888ea4a3fb767dc4ac63268f85636e3a` passed all 165 fingerprints,
14 method requests, seven event polls, native/delivered output and all three
visually inspected captures. Its first installed-status HTTP request took
8.162 seconds; its unchanged SSH status command took 8.103 seconds. The owned
Decky unit stopped with mixed policy, inactive/success state, zero exit status
and MainPID in 2.897 seconds. No observer failure or leak was observed.
Updated exact-head native CI remains required. ARM64
browser, real Steam CEF, managed installation and physical-controller limits
remain unverified.
