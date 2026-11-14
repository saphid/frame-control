# DeckyFileServer child IPC EOF and unload

Main `3ce3a9d33f97775cb44d4f76606d03fb75658284` passed the functional
DeckyFileServer 1.2.0 HTTPS checks, but its AMD64 runtime gate caught a forced
plugin kill. The original unload hook did not run. The parent loader exited
zero, so the strict console gate was necessary to expose the failure.

The failed job is
[130220534310](https://github.com/saphid/frame-control/actions/runs/42928366848/job/130220534310).
Artifact `13814722727` has archive SHA-256
`fda1491810bc9673e9bc64e48ac7eaae150294b6f54e09f54cf24a3fe77ee0ec`.
A local normal-stop run of the unchanged main passed; the ordinary shutdown
failure is intermittent. A private peer-EOF control makes the child IPC
failure reproducible without depending on that timing.

The repair installs the existing child IPC EOF adapter only for the exact
official archive. Its original backend SHA-256 is checked before adaptation;
the previous managed backend remains byte-identical after the small adapter
prefix. Its native helper, HTTPS behavior, root removal and original unload
hook remain intact. Existing managed receipts require Update/reinstall.
Missing adapter payloads fail and roll back installation.

Published Decky 3.3.0 on native AMD64 passed:

- The existing private HTTPS listing/download, upload-denial and thumbnail
  policy checks.
- A settings RPC after explicitly closing a private IPC peer.
- Two parent-only SIGTERM stops, the original unload hook and a restart with
  independently unchanged saved settings.
- An unrelated sibling surviving both stops; all exact owned descendants
  reaped with no forced plugin kill.
- The previous empty-argument thumbnail negative control.
- A new negative control that restores the previous managed backend, closes
  its IPC peer and observes one forced plugin kill without the unload hook.

The native helper is identified by its executable path and process start
ticks before the existing API stops it. Its requested SIGTERM exit can leave
an adopted zombie until loader shutdown. The fixture reaps that exact helper;
it still requires successful loader/Decky child exits and rejects forced
plugin kills. It never signals the plugin child to manufacture a clean stop.

All execution uses disposable networkless containers, private fixtures and
the digest-pinned published loader. No host home, devices, audio, session bus,
real user files or headset are exposed. The focused store, compatibility and
IPC suite passed 131 tests without skips. The three added install/receipt
regressions failed before the repair. The original backend negative control
reproduced the unload failure after the repair was installed and then removed
inside its disposable fixture.

The first hosted macOS run exposed a fixture architecture error: the two new
install tests inherited macOS `arm64` instead of a Linux target architecture.
Both tests now explicitly install and verify `x86_64` and `aarch64` payloads
without executing the Linux helpers. The production architecture checks are
unchanged; these fixture checks are separate from native runtime proof.

The [structured receipt](framey-fileserver-ipc-eof-2026-11-11.json) retains
source bindings and results. The [compressed raw reports](framey-fileserver-ipc-eof-2026-11-11-raw.json.gz)
retain the failed hosted case, original local run and repaired/negative runs.
Hosted candidate and native ARM64 qualification are pending. This reproduces
and repairs the DeckyFileServer child failure; it does not establish the cause
of the separate historical ARM64 migration timeout. Exact-release locked
Frame smoke, worn visibility, physical controller input, scrolling and the
VR keyboard remain unverified. No release gate is cleared by this evidence.
