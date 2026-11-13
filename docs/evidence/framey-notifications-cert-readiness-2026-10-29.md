# Decky Notifications native test readiness, 29 October 2026

The [PR #414 native ARM64 job](https://github.com/saphid/frame-control/actions/runs/40836692223/job/123323018864)
failed after published Decky 3.3.0 reported the exact Notifications plugin loaded.
Its first `local_fingerprint` RPC returned `No such file or directory:
'local.crt'`. The official backend starts certificate creation in `_main`,
while Decky lists the plugin before that coroutine finishes. This is a
readiness race in the native test, not evidence that the Bluetooth evidence
change broke Notifications.

The native case now retries only that exact missing-certificate result within
its existing 20-second readiness bound. Any other RPC failure still raises an
assertion. The same check applies after the private backend restart. No
published plugin, installer, or runtime behavior changed.

Locally, `python3 scripts/framey-test-decky-runtime.py --case 79 --output
/tmp/framey-notifications-cert-readiness-20261029.json` passed with the
published Decky 3.3.0 loader in a disposable network-, device-, and
session-isolated container. It verified private certificate fingerprint,
empty device and notification lists, synthetic notification read/clear, and
fingerprint persistence after restart. The runner removed its owned container
and image. The private JSON report has SHA-256
`f7f9acc3e6ca404868d9541c837cd3bd51d0a77ba8912bafc239144407cb2eae`.
The [exact-head PR #415 checks](https://github.com/saphid/frame-control/pull/415/checks)
passed, including the published Decky 3.3.0 native
[amd64](https://github.com/saphid/frame-control/actions/runs/40837628439/job/123326050682)
and [ARM64](https://github.com/saphid/frame-control/actions/runs/40837628439/job/123326051077)
cases. The same complete native workflow passed on merged main commit
`488720a4c0b4f5cb4f8fffad4a07ec9ffdb2883c` after PR #414 brought the
repair into its branch. The workflow runs every case in
`tests/decky-runtime/cases.json`, including Notifications ID 79, on both
architectures. These isolated container results support the catalog's amd64
and ARM64 backend verification label. Pairing, live notifications, use on the
real Frame, and worn VR remain unverified.
