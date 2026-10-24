# Changelog

## Unreleased

- Fix two cases where optional diagnostic logs could retain part of a headset
  display name or an SSH host name, while preserving existing privacy redaction
  (issue #81).

- Fix experimental PC screen capture on Windows builds whose streaming libraries
  lack Windows Graphics Capture. Whole screens use Desktop Duplication; individual
  windows are hidden with an explanation instead of failing when shown. A Windows
  VM streamed a real desktop to the Frame; physical input remains unverified.

- Add read-only battery health in Tools: charging state, temperature, cycle count,
  and available capacity with explicit unknown states. The parser was checked
  on a real Frame; the connected desktop UI was tested with synthetic readings.

- Add Tools → Game storage: read-only headset filesystem capacity and Steam
  library/game install-size breakdown, with unknown sizes, partial inventories
  and permission/missing-drive states. Includes instructions for Steam's own
  Move UI; Frame Control does not move or delete game files. The read-only
  parser was checked on a real Frame; the connected UI and game moves were not.

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
