# Native ARM Terminal diagnostic branch

This directory is an opt-in investigation for issue #746. The branch
`diagnose/framey-native-arm-unix-nxmf` is not a merge candidate. Its replacement
`.github/workflows/decky-runtime.yml` has only a manual dispatch trigger and one
branch-restricted `ubuntu-24.04-arm` job. Do not merge that replacement into main.
Default-branch workflows and release qualification remain unchanged.

The runner archives exactly main commit
`dd2223e799bb3db8256285e353d5a0ad2f4bd014`, loads its own packer and result codec,
and checks the reviewed observer/helper/bootstrap digests before boot. The
published Decky 3.3.0 ARM loader is pinned by SHA256 and ELF architecture. Docker
builds the exact-main Containerfile on the native ARM runner, including normal
Debian package configuration; its exported rootfs digest and image metadata
and the complete exported TAR are retained as workflow artifacts on success or failure.
The staged TAR is removed only after upload; container and image cleanup remain
immediate. This differs from the earlier extracted-package ARM image and
from cross-architecture TCG on x86. It does not isolate those environment factors
or explain prior failures.

QEMU runs a separate guest with two CPUs and 6144 MiB RAM, TCG, no network device,
no host devices, and no shared host mounts. The unmodified published fixture
runs as guest UID 1100; only the observer runs as root inside that owned guest.
Host tracefs and host user services are never used. Limits stay eight seconds
per RPC, 120 seconds for the native fixture, 180 seconds for the guest service,
240 seconds for QEMU, 16 KiB trace buffer per CPU and one bounded 32 KiB trace
read. Cleanup has separate bounded SIGTERM/SIGKILL waits of eight/five seconds;
those do not extend the observation window. Only the tracked Popen group and
its task-owned boot files are removed. Original execution errors survive cleanup
failures, which remain failed and are recorded in `assessment.json`.

The result reports execution, capture completeness and qualification separately.
`qualificationPassed` is always false. The observer covers filtered driver
invocations and normalization events, including stream and seqpacket paths; it
cannot establish universal syscall coverage or event-time PID/start identity.
Capture-end task availability is a separate fact. Event endpoint names are hashed;
raw trace text and kernel pointers are not retained. The ordinary fixture's
synthetic input/output and startup logs are retained for source-bound analysis.
No real Frame, browser interaction, wearer or controller proof is established.

The observer/helper/bootstrap bytes are copied unchanged from the separately
reviewed private sources: observer `14c6d0bc218b09e187995a1973efd497902fe125f9afebcbc8104a64589afcb5`,
helper `d0610c3eb26b5af7a5a2d0f9f020f8b7829e6b816b5261dcaaf3ba1419f53053`,
bootstrap `1e5e9ff9d348a649a5704c3ad26f9fd022bb9cc10c2c0308e518bdefee7e6512`.

Pure host fault controls (no VM, loader, tracefs or network):

```sh
python3 -m unittest discover -s tests -p test_framey_native_diagnostic.py -v
```

The sealed original main Terminal ARM eight-second RPC failure, HTTP sixty-second
readiness failure, cross-architecture 240-second observation failure and all
release/headset holds remain in force. A successful instrumented observation
would supply a diagnostic timeline, not qualify main or establish a repair.
