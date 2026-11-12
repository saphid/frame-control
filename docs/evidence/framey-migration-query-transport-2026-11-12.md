# Migration observer query transport

The opt-in migration-stack run for #677 retained eight `runuser` query
timeouts on ARM64. The error list is capped at eight, so this is not a total
timeout count. Its running baseline includes a ready parent event loop and a
plugin sandbox still importing SSL/aiohttp. No shutdown-window sample was
captured. This does not explain the historical migration shutdown timeout.

The first `setpriv` implementation at `bd854a6177` also retained eight query
timeouts in the actual ARM64 migration. That service stopped normally in
14.606 seconds; the transport change did not eliminate the diagnostic errors.

Read-only observer queries now use a persistent Python D-Bus client, launched
once through `setpriv` with UID/GID 1100 and no supplementary groups. It only
reads the migration unit's state, cgroup, main PID and stop budget. Requests
retain their three-second deadline and have a 4,096-byte reply limit. Startup
is bounded at 15 seconds; timeout, malformed replies and probe failure reap the
helper. Expected unit disappearance is distinct from a bus failure. The actual
unprivileged migration probe, sampling identity checks and strict 90-second
service-stop budget are unchanged.

A disposable AMD64 systemd VM compared three queries through each transport
against the same published Decky service. All six succeeded and returned
identical properties. These few timings do not establish an ARM64 performance
improvement. A root-credential query with only the tester's bus environment
was separately rejected by systemd; that shortcut is not used.

The changed observer also captured an identity-bound Python baseline in this
VM, reported no query errors, joined both observer and query helper, and
observed a clean service stop.
The [record](framey-migration-query-transport-2026-11-12.json) binds the changed
source files, sampler and raw archive. The
[compressed raw record](framey-migration-query-transport-2026-11-12.raw.json.gz)
retains the guest result and both fixture programs. The owned QEMU and
temporary boot files were removed. All 98 focused tests passed without skips.

This empty-plugin feasibility test did not execute the Syncthing migration
or ARM64. Both native actual-migration runs remain required for the changed
observer. It does not establish the historical shutdown cause, clear a
release hold, or replace the locked exact-release real Frame smoke.
