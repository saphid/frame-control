# Published loader parent stacks during controlled EOF

An external sampler observed the unmodified published AMD64 Decky 3.3.0
parent repeatedly executing `PluginWrapper._response_listener`, the Unix
socket reader and JSON decoding during the controlled child-exit hang. The
normal-shutdown control passed in 0.314 seconds. After abrupt child exit, HTTP
timed out and parent SIGTERM did not complete within eight seconds. Every
owned process was reaped after the corrected experiment.

This identifies where this controlled published-binary reproduction spins.
It does **not** establish that the same event caused the historical ARM64
migration timeout. No ARM64 user-space stack or historical VM stack was
captured, and no release gate is cleared.

## Evidence and provenance

[`receipt.json`](receipt.json) records all input and artifact SHA-256 values.
The original fixture is `tests/decky-runtime/parent_eof_native.py` at exact
source head `c80dda3374b9ffce22227337d669cb8432b6fc97`. The loader SHA-256 is
`e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181`.
The sampler is the digest-verified AMD64 Linux wheel from py-spy v0.4.3;
its release URL, wheel digest and extracted executable digest are retained.

The sampler launched its own Python fixture and followed only that process's
descendants. It ran at 50 Hz with `--subprocesses --threads --nonblocking`,
inside a networkless, read-only, unprivileged disposable container with all
capabilities dropped. No host PID namespace, devices, audio, session bus or
home directory were exposed. Sampling neither paused the target nor added
capabilities or changed a system security setting. The pinned repository,
loader, sampler and fixture were read-only mounts.

The abrupt run's loader parent was PID 35; the receipt binds it to its
recorded parent PID and `/proc` start ticks. There are 65 distinct stack groups
and 229 weighted samples for that exact process in `_response_listener`.
The retained stacks include `plugin.py:94` through the socket reader and
`plugin.py:96` through JSON decoding, including JSON decode exceptions.
These agree with the EOF/JSON retry mechanism in the source-level probe.
The sampler did not record local variable values.

The complete run reported 773 samples and 99 sampling errors across its
tracked processes. Nonblocking samples can be inaccurate; no claim of full
coverage, exact CPU percentage or complete stack capture is made. The
unmodified parent, failed HTTP request, missed SIGTERM deadline and observed
CPU progress are also recorded independently by the fixture.

## Cleanup control and the retained failed attempt

The first sampling attempt failed its cleanup control. The original fixture
expected to be container PID 1, but the sampler became its ancestor. Orphaned
loader descendants were adopted outside the fixture, so its `waitpid` calls
could not reap them. That attempt is retained as
`failed-initial-sampling-report.json.gz`; it is not passing shutdown evidence.
Its disposable container was removed.

The corrected private fixture sets `PR_SET_CHILD_SUBREAPER` on itself before
launching the loader. This changes only adoption of its own orphaned
descendants, allowing the existing exact-PID/start-tick reaper to operate
when the fixture is below the sampler. It does not alter the published
loader, plugin transport, test deadlines or production code. Both the normal
control and final owned-process reaping passed in this corrected run. The
source snapshot is retained as `probe.py.gz` and the outer sampling wrapper
as `sampler-wrapper.py.gz`.

## Retained files

- `successful-sampling-report.json.gz`: full sampled-run report, native
  fixture reports, loader consoles and raw stack text.
- `stacks.raw.gz`: the same complete raw stack file, independently hashed.
- `probe.py.gz` and `sampler-wrapper.py.gz`: exact private experiment sources.
- `failed-initial-sampling-report.json.gz`: the rejected first harness run.

All gzip files use a zero timestamp for deterministic encoding. Verify their
compressed and decompressed bytes against `receipt.json` before use. The
wrapper contains the exact sampler invocation. To repeat the experiment,
use the existing `tests/decky-runtime/Containerfile` on native AMD64 Linux,
the pinned inputs from the receipt, and the same isolation flags as
`scripts/framey-probe-decky-native-parent-eof.py`. Mount the unpacked private
fixture at `/input/probe.py`, the verified sampler at `/input/py-spy` and the
wrapper at `/trace.py`; run the wrapper as the container's unprivileged user.
Only the unique owned container and image are eligible for removal.

No headset was contacted. The historical ARM64 cause and locked exact-release
Frame smoke remain release holds. Worn visibility, physical controller input,
scrolling and the VR keyboard remain unverified.
