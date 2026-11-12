# Migration observer query transport

The opt-in migration-stack run for #677 retained eight `runuser` query
timeouts on ARM64. The error list is capped at eight, so this is not a total
timeout count. Its running baseline includes a ready parent event loop and a
plugin sandbox still importing SSL/aiohttp. No shutdown-window sample was
captured. This does not explain the historical migration shutdown timeout.

Read-only observer queries now use `setpriv` with UID/GID 1100 and no
supplementary groups. It replaces itself with `env` and then `systemctl`,
avoiding a PAM session and a persistent `runuser` parent for every query. The
actual unprivileged migration probe retains its existing launch command.
The three-second query deadline, sampling identity checks and strict
90-second service-stop budget are unchanged.

A disposable AMD64 systemd VM compared three queries through each transport
against the same published Decky service. All six succeeded and returned
identical properties. These few timings do not establish an ARM64 performance
improvement. A root-credential query with only the tester's bus environment
was separately rejected by systemd; that shortcut is not used.

The changed observer also captured an identity-bound Python baseline in this
VM, reported no query errors, joined, and observed a clean service stop.
The [record](framey-migration-query-transport-2026-11-12.json) binds the changed
source files, sampler and raw archive. The
[compressed raw record](framey-migration-query-transport-2026-11-12.raw.json.gz)
retains the guest result and both fixture programs. The owned QEMU and
temporary boot files were removed. All 93 focused tests passed without skips.

This empty-plugin feasibility test did not execute the Syncthing migration
or ARM64. Both native actual-migration runs remain required for the changed
observer. It does not establish the historical shutdown cause, clear a
release hold, or replace the locked exact-release real Frame smoke.
