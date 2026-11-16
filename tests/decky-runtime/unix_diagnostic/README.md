# Native ARM Terminal diagnostic branch

This opt-in investigation for issue #746 lives only on
`diagnose/framey-native-arm-unix-nxmf`. Do not merge the branch or replacement
workflow into main. It has one manual `observe=true`, exact-branch-restricted
`ubuntu-24.04-arm` job, read-only contents/actions permissions and no cancellation.

The runner archives fixed accepted main
`dd2223e799bb3db8256285e353d5a0ad2f4bd014`, uses its exact packer/result codec,
and checks all eight reviewed payload digests and the published Decky 3.3.0 ARM
loader SHA256/ELF machine. This revision reuses retained rootfs artifact
`14201758003` from original run `43814749117`. It requires rootfs SHA256
`2f5bd5c38043a9a79b7cad7c7574b54360a5186ad7437d171ff808088dfa841c`;
there is no new Docker build or rootfs preparation. That immutable original
artifact remains the exact input proof on success/failure. New report evidence
is always uploaded before the task-owned staged copy is removed.

QEMU runs a networkless owned guest with 2 CPUs/6144 MiB, TCG, no host devices
and no shared host mounts. The observer runs as guest root; the private driver
runs as UID1100 and imports identical check.py source before explicitly calling
its original main with 65/-/--terminal-candidate. This adds a different module
namespace, driver frames and instrumentation; uninstrumented equivalence is
not claimed. Main's published fixture and default workflow bytes stay unchanged.

The synchronous adapter observes the existing loader Popen, fixed token HTTP
and published-discovery calls. It adds no network request, sampler thread or
process. Passive bounded `/proc/net/tcp` reads occur only at existing token
boundaries at least 500 ms after the previous read completed. Listener records
describe only the guest IPv4 loopback/wildcard port1337 network namespace;
no process ownership, exact bind time or continuous readiness is established.
Read start/end and later record clocks are separate. Timing perturbation is
possible and negligible overhead is unproved.

`token-http-returned` means urlopen returned response HEADERS only. Original
body read/decode happens afterward and may fail/block. Token-body completion,
authentication, discovery or WebSocket readiness is not implied. No WebSocket
stage hooks are installed. The source-defined discovery20 deadline is checked
before each read; an in-flight late positive return still succeeds unchanged.
All original values, exceptions and stage timeout arguments remain forwarded.

Observation records are limited to256 and32KiB, with read16385 sentinel bounds.
The original native report has its own32KiB sidecar cap. Disabled hooks perform
no passive reads or sidecar writes. Fixture globals are isolated by proxies,
with stdlib globals untouched, and restored in finally. Original failure reports
are retained after original cleanup, without converting failure to success.

The guest collects three fixed source-bound sidecars after owned cleanup,
including failed probes. The reader requires no-follow/nonblocking regular
files, UID1100/mode0600/single-link, unchanged stat metadata and a32769-byte
maximum read. It refuses duplicate keys, nonobject/nonfinite JSON including
exponent overflow, partial bytes and receipt hash/size mismatches. Missing or
incomplete evidence remains unavailable. Observer/manager cleanup errors remain
separate failures and cannot bypass collection. Packet/device failures still
fail at the VM bound. A complete sidecar or capture never establishes native pass.

Unchanged bounds: RPC8/discovery20/HTTP60/native120/service180/VM240 seconds;
manager stop40; trace ring16KiB perCPU/read32KiB. Owned host cleanup uses separate
TERM8/KILL5 waits without extending the observation window, preserves execution
errors, and finalizes evidence/boot-file removal after cleanup failures.

The kernel observer/helper remain14c6/d061. They cover filtered Unix driver
invocations and normalizations, not IP discovery or universal syscall coverage.
Capture-end availability does not prove event-time task/start identity. No raw
trace lines, arbitrary endpoint names or kernel pointers are exported. The
ordinary native report retains its original console fields independently.

Run pure fault controls from the repository root (no VM/network/loader):

```sh
python3 -B -m unittest discover -s tests -p test_framey_native_diagnostic.py -v
python3 -B -m unittest discover -s tests/decky-runtime/unix_diagnostic -p 'test_*.py' -v
```

Source review e33884f7 approved the exact runtime payload/runner/workflow and
replayed10guest/transport+9runner+1rootfs controls, plus8independent fault
methods and3architecture controls. The initial exponent-overflow finding and
red evidence remain sealed separately. Final publication/source checks and a
fresh no-duplicate guard must precede a single changed observation.

Original main Terminal8s/HTTP60s failures and the original native diagnostic20s
discovery failure remain failed. This diagnostic supplies observations, not a
historical-cause, repair, main, release, actual Frame, wearer/controller or VR
claim. All qualification/release/headset holds remain in force.
