# ARM64 migration shutdown failure

Exact #566 head `1c781ac9189607deb6ac2bcdbaf45928795a3eae` failed the
[ARM64 signed-package job](https://github.com/saphid/frame-control/actions/runs/42163869222/job/127715639322).
Artifact `13480060906` is retained outside the successful-artifact inventory.
Its uploaded digest, producer checkout, member digests and committed source
fingerprints were independently verified. The [JSON record](framey-migration-stop-timeout-2026-11-06.json)
contains the bindings and observed service state.

Signed package installation and private two-way synchronization completed.
During migration cleanup, systemd's 90-second stop budget expired and killed
the owned migration Decky fixture. Its recorded stop took 96.588 seconds,
with `Result=timeout`, `ExecMainCode=2` and `ExecMainStatus=9`. This is a failed
package gate, not a clean shutdown or a presumed infrastructure flake.
The owned QEMU was reaped and its disposable boot images were removed.

The fixture's stop assertion bypassed the rest of its `finally` block,
including log verification and cleanup of its deliberately unrelated sleeper.
That sleeper inherited the migration subprocess's captured output pipes.
The outer command consequently timed out at 360 seconds, obscuring the
earlier assertion. The retained artifact does not contain the Decky loader
log needed to establish why the service hung.

The follow-up fixture change uses `ExitStack` to run remaining cleanup and
log verification even when a stop fails. Its unrelated sleeper no longer
inherits captured output. Neither the systemd stop budget nor strict result,
exit-status, process-reaping or loader-log assertions are relaxed.
The original failure still propagates; log failures retain it as exception
context. This repairs lost diagnostics and skipped fixture cleanup. It does
not establish a fix for the underlying Decky shutdown hang.

Three local regression cases execute the actual migration cleanup block:
failed stop, failed stop plus bad log, and normal stop. Against the original
fixture, both failure cases fail and the normal case passes. The updated
fixture passes all three. These are controlled failure-path tests, not an
ARM64 runtime pass. Fresh hosted qualification and investigation of any
retained shutdown errors remain required.

Exact main `8714e7bba629b1c2c00e0a94264670bc20721200` independently passed all
16 checks and all nine artifact audits, including its ARM64 package job.
That separate pass does not dismiss this failure or qualify a new #566 head.
No real Frame, wearer-visible UI, physical-controller test or release was
performed. Syncthing remains a test candidate with managed installation disabled.
