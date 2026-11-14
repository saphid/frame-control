# Windows Speed Test fixture timeout

PR #497 at `f411ab5` failed Windows job `124317049737` in checks run `41129662192`: its Node Speed Test replay exceeded 10 seconds. No subprocess output was retained in the exception, so startup, Response initialization, body reads and shutdown cannot be distinguished. This is an unclassified failure, not a Notebook backend failure or a proven runner flake.

Main `e26ae7f` independently passed the same committed test bytes in Windows job `124322238705` in about 0.4 seconds. All seven focused audit-browser tests pass locally under Node 24.15.0; the failed runner used 24.22.1. These results do not override the failed job or establish its cause.

The test now emits elapsed stage markers and reports captured output on timeout, including whether assertions finished before process exit stalled. All behavioral assertions, real Response body consumption and the 10-second deadline remain unchanged. A controlled TimeoutExpired confirms this still fails and retains the last completed stage. No production source, network behavior or deadline changes.

The adjacent JSON retains log hashes and the local stage output. Fresh Windows validation is required. Current package CI is allowed to finish before any diagnostic update is pushed; no live workflow is cancelled. No Frame, Steam CEF, wearer-visible or controller proof is claimed.
