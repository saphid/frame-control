# Main CI recovery, 29 October 2026

PR #405's exact head `38242a2bd383db200e383ec80db134ca03273f6c`
passed all 12 hosted checks, including e2e and native Decky on both
architectures. The GitHub merge request then returned HTTP 502. GitHub's main
ref advanced to signed merge commit
`f5086267619fd6ea11c085af59e9841b5f12bbde`; its tree exactly matches
the green PR head. GitHub still reported the PR open, and the Actions API
returned zero runs for that main commit. A pinned retry was rejected as not
mergeable. A non-force update of main to its existing SHA did not create a run.

The `checks` and `Decky backend runtime` workflows accept only push and pull
request events in that commit. A manual `checks` dispatch was rejected with
HTTP 422 because the trigger was absent. This change adds manual dispatch so
the same hosted jobs can run on an exact main SHA after an event delivery
failure. It does not change test commands, release gates, or the requirement
for successful tagged installer builds. Main and releases remain held until
the relevant exact-commit gates pass.
