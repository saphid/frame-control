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
