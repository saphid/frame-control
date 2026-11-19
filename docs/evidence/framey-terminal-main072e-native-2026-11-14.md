# Terminal candidate refresh against main, 2026-11-14

PR #490 now integrates main `072e7284` while retaining the original Terminal
import blocker and the separate opt-in private candidate. The historical
2026-10-30 evidence and dependency fixtures remain byte-for-byte unchanged.
Current native ARM64 and full-inventory CI must qualify the refreshed head;
prior ARM64 green results are historical evidence only.

The current published Decky 3.3.0 AMD64 binary passed both separate native runs
in the accompanying source-bound JSON. All 66 candidate and 54 original-failure
source fingerprints were compared with the tested tree. The candidate uses the
current runtime Client transcript API, pinned loader input cache, and exact PR
head checkout. The candidate also runs the existing primary shutdown-console
gate instead of being treated as a negative control.

The inherited synchronous `waitpid` workaround raced asyncio's child watcher
and logged an already-read exit status and PTY read exception. The candidate
now installs the existing child-only IPC EOF repair into the disposable copy,
awaits the owned subprocess and worker tasks with bounded asynchronous waits,
and treats EIO/EBADF as EOF only while deliberately shutting down the PTY.
Unexpected I/O errors still propagate. This adds no production installation
adapter or compatibility claim.

Observed in the refreshed AMD64 run:

- Actual private PTY input, separate stdout/stderr and marker-file bytes passed.
- Actual `stty` size was 31 rows by 97 columns.
- Explicit removal and actual Decky plugin reload reaped the recorded shells;
  unrelated private sleep survived reload and private configuration persisted.
- The CPython 3.14.8 extension loaded from the isolated candidate package.
- Final loader parent-only SIGTERM exited zero with no forced process-group
  signal or forced kill, and no asyncio reaping/PTY-read warnings. The generic
  runtime capture's `cleanShutdownVerified=false` remains diagnostic; this is
  not a claim of a stronger complete-descendant shutdown audit.
- The unchanged production archive separately reproduced missing `termios`,
  without backend RPC, PTY commands or input.

Seven coverage/IPC unit tests passed. All 38 existing main probe bodies, the
runtime case inventory, installer, child IPC helper, official archive records,
fixture licenses/dependencies and historical evidence were preserved.

Both executions ran nonroot in disposable read-only, networkless containers.
No headset contact, browser verification, physical input or worn VR test was
performed. Production Terminal remains unsupported by this candidate.
