# ARM64 combined-browser gate preparation, 30 October 2026

The existing combined browser driver and private root bootstrap explicitly
refused ARM64. Native signed-package and Decky backend CI could therefore pass
without exercising ARM64 browser controls. This follow-up removes those two
architecture exclusions and adds a native `ubuntu-24.04-arm` browser/HTTP job.
Both existing package-only jobs and the AMD64 browser/HTTP job remain required.

ARM64 browser mode uses the existing native ARM64 limits: 900 seconds for
installation, 2,400 for the user probe, 2,460 for the systemd unit and 2,520 for
the outer emulator. No deadline is raised. AMD64 retains its current browser
budget. Source-bound native helpers, exact signed bundles, renderer sandbox,
actual RPC/control results, source hashes, preserving uninstall and owned
cleanup requirements are unchanged. The optional production-parent mode is
still excluded from this workflow.

Local validation passes 25 package tests, nine HTTP/fixture tests and three
cleanup tests. New coverage checks that native ARM64 browser arguments reach
the QEMU prerequisite check and that host/guest budgets agree for all four
architecture/browser combinations. No ARM64 browser runtime pass is claimed.
Fresh exact-head native CI and independent capture/artifact audits are required
before crediting that missing proof. The existing replay uses a separate frozen
checkout and was not changed or restarted.

Syncthing installation remains blocked. Managed install/update/remove,
production Steam CEF, real Frame visuals and physical controllers remain
unverified. No real Frame contact or release occurred.
