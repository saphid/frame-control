# Exact native gates for the #480 merge, 30 October 2026

#480 merged as `c1968b1b832ee7aff9d37ea94ca5e2aa79ee4774` after exact main
`24c6acd778fe3aba4936c532793523fa4780716b` passed 14/14 checks and exact PR head
`6d1fac71b7a442d35653f2b673bcd89090b079f3` passed 17/17. Both included e2e and
native Decky AMD64/ARM64. The branch contained current main; mergeability was
clean, with no comments, reviews or unresolved threads. Squash merge matched
that exact head. A fresh GraphQL rollup confirmed main after the REST check-run
endpoint returned HTTP 500 twice; the failed reads did not authorize a merge.

The [five independent artifact audits](framey-syncthing-http-merge-480-2026-10-30.json)
verify both architectures on both heads plus the PR's AMD64 browser/HTTP result:
source fingerprints, signatures/content, actual Syncthing 1.27.3 and Decky 3.3.0,
two-way sync, setup, ownership refusals, lifecycle, migration and data-preserving
uninstall. The HTTP audit reconstructs the packed UI from 105 exact git sources
and verifies 122 source fingerprints, five authentication/receipt/shim refusals,
seven successful CEF RPCs, one socket with unique IDs, and owned cleanup.

The separate private-bridge browser phase had 70 RPCs and four previously
inspected Running/Stopped/Running/Stopped captures. These do not prove the full
production browser parent. At the time of this merge, that excluded development
replay had failed and its cause was unestablished. Fixture CEF and the store receipt are synthetic.
ARM64 browser/HTTP, actual Steam CEF, managed install/update/remove, real Frame
visuals and physical controllers remain unverified. Installation stays blocked.
No new release or hardware contact occurred. Postmerge main CI is a new gate;
these premerge results do not grant a postmerge or release pass.


## Later local parent result

The parent-failure statements above record the state at the audited merge.
Later strict local AMD64 replay12 passed at private source `a4f37b6`, with all
123 source fingerprints and eight captures independently checked. It used
synthetic CEF/receipt data and did not establish ARM64 parent, actual Steam CEF,
managed installation, real Frame or physical-controller behavior. The published
follow-up [#486](https://github.com/saphid/frame-control/pull/486) carries the
candidate, durable evidence and a separate exact-head production-parent CI gate.
Its published-head results must pass independently. Installation remains blocked.
