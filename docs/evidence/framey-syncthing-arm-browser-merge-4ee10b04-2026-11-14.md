# Syncthing ARM64 browser accepted merge, 14 November 2026

PR #483 merged as `4ee10b04` after all 19 exact-head hosted checks passed.
All 85 focused tests and two actual Chromium startup tests pass on current
main, including the full pinned frontend with the Framey runtime and the
normal, delayed-parent and large-child delivery conditions. GitHub's merge
tree and both parents exactly match the tested integration.

All five downloaded signed-package artifacts independently match their sizes
and ZIP digests. Exact-head and guest source bindings verify, including the
137/132 browser bindings on each architecture and 138/133 bindings for the
AMD64 production-parent path. All three transported guest packets decode to
their retained reports. Signed install/signatures, two-way file hashes, service
restart, certificate/data preservation, migration, refusal of unrelated units
and owned cleanup verify. Both architectures' full native and Terminal-candidate
artifacts also pass independent source/loader/console audits.

All 16 browser captures were inspected: running, stopped, restarted and stopped
states appear in the three child runs and the AMD64 production parent. The
ARM64 migration and managed-candidate Decky stops succeed in 10.435s and
9.763s. The earlier failing ARM64 report remains retained; passing this head
does not prove its readiness cause or the historical shutdown cause.

Managed installation remains disabled. Synthetic receipt/input/CEF and private
networkless VMs do not prove real Steam CEF, ARM64 production parent, live
Frame, physical controller, scrolling, VR keyboard or worn visibility.
