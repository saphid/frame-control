# Changelog

## Unreleased

- Add `scripts/frame-doctor.sh` for read-only setup and pairing diagnostics,
  with verified SSH identity, private summaries and actionable next steps
  (issue #34). Connection steps links to the diagnostic guide. Repairs remain
  manual; restart-loop evidence stops deeper diagnostics. The real Frame
  verified the SSH connection and safety stop; deeper checks were skipped.
