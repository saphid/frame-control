# DeckyParty user-service lifecycle, 30 October 2026

The official store still publishes **DeckyParty File Manager 1.0.0**, ID **117**,
with SHA-256 `193fb3aa0446fbc3c6bae0ae15700b5f04acebfa917b8e1791988c6ce832dddf`.
A fresh store read confirmed the same version and digest. Its original `main.py`
has SHA-256 `807abacba8359bfd87763bc4e32a40b89ca6ca84bb778d29bc062fbd4f0686b2`.
The bundled, pure-Python Copyparty 1.19.21 helper has SHA-256
`e88f0327739c85dcd382048244942c668669cc2dd92db64e1aebf425981f7310`.

## Failures and change

The original backend asks `sudo` to run as an environment-selected user even
though Decky's managed service already runs as that user. `_stop_process`
signals its child and immediately drops the handle, without waiting for exit.
It also lacks `_unload`; repeated `_main` calls create extra runner tasks.
Private lifecycle contracts reproduced five failures before adaptation.

Only this exact archive receives `deckyparty-user-lifecycle`. The installer
checks its Python source hash and changes the backend to:

- Use the actual UID's username and current home, invoking the original helper
  with `/usr/bin/python3`. Loader-specific Python/library environment variables
  are removed only from the owned child's environment.
- Defer annotation evaluation so the managed backend also imports under the
  host's minimum Python 3.9. The first CI head failed there on upstream's
  `str | None` annotation; the corrected install and seven lifecycle contracts
  pass in a read-only, network-isolated Python 3.9 container.
- Keep Copyparty's temporary extraction cache inside plugin runtime storage,
  avoiding the shared global `/tmp/pe-copyparty.*` cache cleanup.
- Start the helper in its own process session, terminate only that process
  group, wait up to three seconds, and kill/reap its owned group after timeout.
  An exited child is reaped before its handle is cleared.
- Keep one runner, require a Boolean enable request, and cancel/await the
  owned runner before stopping its helper on unload. Awaiting the task directly
  passes actual Decky unload; a first `gather` implementation exceeded Decky's
  five-second shutdown deadline and was replaced before submission.

The original frontend, helper, manifest and LICENSE stay byte-identical.
The server stays disabled by default. Upstream authentication, volume
permissions and TLS configuration are unchanged. Enabling still serves the
user's home and discovered external media as the upstream plugin specifies.
Existing managed copies require Update/reinstall.

## Verification

Seven direct lifecycle contracts pass with private paths, including actual
child reaping while an unrelated child survives, timeout escalation, repeated
startup/unload, malformed enable requests and child environment/cache scope.
The managed install test also checks preserved payloads and digest scope.

[Published Decky 3.3.0 x86_64 evidence](framey-deckyparty-native-2026-10-30.json)
comes from an unprivileged container with no external network, host devices,
user session or writable host bind mount. Its home is an owned anonymous
Docker volume removed with the container. Copyparty correctly refused uploads
to the original tmpfs fixture; the test changed storage rather than disabling
that guard. The original helper and real legacy RPCs verify:

- Disabled discovery, actual `tester` username and temporary home.
- Authenticated listing and independent download bytes; anonymous and
  incorrect-password reads cannot obtain the private file.
- Upload bytes read independently from disk, restart/readback, and deletion of
  that uploaded fixture while another private file remains unchanged.
- Disable removes the listening server and all matching helper processes.
- Decky's real reload calls `_unload`, closes the server, leaves no matching
  process and starts a disabled plugin. No forced Decky SIGKILL occurs, and
  an unrelated private child survives.

The reload endpoint queues work. The probe waits for Decky's completed reload
log before making another backend RPC, avoiding the old wrapper's closing
response listener. Credentials generated inside the fixture are omitted from
the committed report. Containers, anonymous volumes and the runner's image
are removed by the harness.

The same case passed [native AMD64/ARM64 CI](https://github.com/saphid/frame-control/actions/runs/40999192658)
on head `bdeb347e20c11fc22723f82337ce5fc0500e4acb`, first attempt.
The [ARM64 artifact excerpt](framey-deckyparty-native-arm64-2026-10-30.json)
identifies the exact workflow/head/loader and records the same independent
file-operation and lifecycle checks. That head's Python 3.9 failure was fixed
afterward; the new exact-head CI remains a merge gate.
The next head `4d28468` could not start that job: `ubuntu-latest` selected
Ubuntu 26.04, for which setup-python publishes no Python 3.9 x64 build.
Its published versions manifest lists 22.04 and 24.04 for Python 3.9.25.
The minimum-version job is now pinned to Ubuntu 24.04; the Python baseline
and all test steps are retained. New exact-head CI must verify this change.
Three fake-Frame HTTP/SSH install/update/remove tests passed
in 72.393 seconds and their uniquely named project/volumes were removed.
The full local suite passed **1,774 tests, 16 skips, zero failures** in
209.697 seconds. The first run found the missing runtime-probe inventory entry;
that entry was added before this passing run. Fifteen compatibility lookup/doc
checks also pass after updating the table; generated docs and diff checks pass.
The subsequent [full-catalog transport audit](framey-catalog-transport-2026-10-30.md)
also passes all 116 pinned archives. No new frontend behavior or browser
evidence is claimed.

## Limits

DeckyParty stays **partial**. New exact-head CI must pass before merge. Real Frame
managed execution, LAN/HTTPS behavior, external media, real user files,
panel enable/password presentation, wearer-visible rendering and physical
controller use remain unverified. No real Frame was contacted. The separate
locked headset schedule and all exact-commit release gates remain in force.
