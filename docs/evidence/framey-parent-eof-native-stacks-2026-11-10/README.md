# Native ARM64 and AMD64 parent stacks during controlled EOF

Digest-verified hosted artifacts at exact source head
`2695b3a2c8a70b36695752276256a33a9e6c1442` captured the unmodified
published Decky 3.3.0 parent executing `_response_listener`, socket reads and
JSON decoding during deliberately abrupt exit of its private synthetic plugin.
The native ARM64 parent has 246 listener samples across 77 stack groups;
AMD64 has 243 across 74. These are stack sample counts, not CPU percentages.
The normal controls stopped cleanly in 0.290 and 0.214 seconds, respectively.
After abrupt child exit, HTTP timed out and parent SIGTERM missed its existing
eight-second budget. All owned processes, containers and images were removed.

The sampler reported 686 total samples and 73 sampling errors on ARM64, and
724 samples and 95 errors on AMD64. Nonblocking sampling can be inaccurate;
these observations do not claim complete coverage. Socket, stream and JSON
frame-family counts overlap and must not be added as exclusive categories.

These results identify frames in the controlled native ARM64 reproduction.
They do not show that EOF caused the historical ARM64 migration VM timeout,
reconstruct its missing loader log, or clear a release gate. Locked smoke on
the exact release remains incomplete. No headset was contacted, and worn
visibility, physical controller input, scrolling and VR keyboard are unverified.

## Provenance and repetition

[receipt.json](receipt.json) binds each original GitHub artifact and producer
job, uploaded archive digest, owned parent identity, sampled frame counts and
retained file digests. `*-report.json.gz` includes the published loader and
sampler wheel/executable hashes, source fingerprints, controls and cleanup.
`*-exact-head.json.gz` binds the report and raw stacks to the original checkout.
`*-container.log.gz` preserves the original probe output and sampler errors.
All retained gzip timestamps are zero. Verify both compressed and raw digests
before using this evidence; the original artifact ZIPs remain in the local
build-watch evidence store and on GitHub while retained there.

Repeat with `scripts/framey-probe-decky-parent-stacks.py` on native Linux AMD64
or ARM64, or the `Decky parent EOF stack samples` workflow. The diagnostic
keeps the container networkless, read-only and unprivileged. It adds no
capabilities, host PID namespace, devices, audio, home or session bus. Only
the private probe adopts its orphaned descendants below the sampler; neither
the published parent nor transport is changed. A new integration head requires
its own fresh hosted qualification; this receipt always describes the original
source head above.
