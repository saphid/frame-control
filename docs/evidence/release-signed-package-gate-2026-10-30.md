# Signed-package publication gate, 30 October 2026

The publisher previously required exact-commit main checks, native Decky
checks and tagged installers, but did not inspect the signed Syncthing
package workflow introduced after v0.4.56. A missing or failed package run
could therefore pass the publisher's dry run.

The gate now requires the AMD64, ARM64, browser HTTP and production-parent
HTTP package jobs at the
exact tagged commit on `main`, from a push or manual dispatch. It checks
every matching run and every attempt; missing jobs, stale commits, other
branches, PR results, unfinished jobs, failures, cancellations and skips
refuse publication before an upload, delete or release update. A manual
dispatch is needed when a version-only commit does not match path filters.

Local validation used the publisher with the repository's fake GitHub CLI,
temporary Git checkouts, fixture smoke results and fixture installer audits.
Before the gate change, the two new regression methods reported 16 failed
subcases: 14 invalid package states were accepted, and the two successful
paths never inspected package runs. After the change, all 21 publisher
tests and all 12 release-workflow tests passed. Syntax and diff checks passed.
No test contacted GitHub, published a release or used the real Frame.

After #486 merged, the branch was updated onto main `043085b` and the new
production-parent HTTP job was also made mandatory. Its absence has a
separate refusal case, and failed-state tests now check that the error names
the signed-package gate. The original red-phase count above precedes this
additional case.

This adds an automated release precondition. It does not establish an
installed Syncthing adaptation, Steam CEF, physical-controller usability or
wearer-visible UI. Exact-head PR CI is still required before merging, and
the other release gates remain required before publishing.

## Separate main and native workflow runs

A further review found that main checks and native Decky used only their
newest separate push run, although all attempts of that run were inspected.
A newer successful run could therefore conceal an earlier failed, cancelled,
skipped or still-running workflow at the exact same release commit.

The new end-to-end publisher regression reproduced ten invalid states being
accepted by the fake publisher: those four workflow states and a failed job
under a successful workflow summary, for both main checks and native Decky.
A separate positive test also failed because neither earlier successful run
was inspected. The 23-method red run reported 11 failures in 50.357 seconds.
These fixtures used temporary checkouts and fake GitHub responses; no actual
release mutation occurred.

All four required workflow families now use the same complete exact-run
enumeration and per-attempt job verification. Main/native still require main
push results; signed-package results permit push or manual dispatch; tagged
installers still require the exact tag push. The extra inspection does not
accept another branch, commit or PR run, or relax an existing smoke/package
condition. The updated publisher passed all 23 tests in 39.983 seconds; all
12 release-workflow tests passed in 0.977 seconds. Python compilation and diff
checks passed. Exact-head CI remains required and current-main repair #491
still has priority over this merge. No real release or headset was changed.
