# Changelog

## Unreleased

- Add Tools → Game storage: read-only headset filesystem capacity and Steam
  library/game install-size breakdown, with unknown sizes, partial inventories
  and permission/missing-drive states. Includes instructions for Steam's own
  Move UI; Frame Control does not move or delete game files. The read-only parser was
  checked on a real Frame; the connected UI and game moves were not.

- Add `scripts/frame-doctor.sh` for read-only setup and pairing diagnostics,
  with verified SSH identity, private summaries and actionable next steps
  (issue #34). Connection steps links to the diagnostic guide. Repairs remain
  manual; restart-loop evidence stops deeper diagnostics. The real Frame
  verified the SSH connection and safety stop; deeper checks were skipped.
- Fixed headset smoke cleanup reporting success while a smoke-title process
  could remain running after its files were removed. Cleanup now stops and
  rechecks processes tied to exact reserved test-title paths, uses PID handles
  for safe TERM/KILL escalation, and records stopped PIDs. Unrelated titles and
  shared Wine services are left alone. Verified with local Linux process
  regressions and a 13/13 real Frame smoke run that stopped five test-owned
  Proton process PIDs before removing the Windows test title.
