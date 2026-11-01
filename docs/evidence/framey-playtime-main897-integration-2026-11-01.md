# PlayTime integration with TabMaster recovery

Implementation `de60ed83450f737f746761c3394df12853bfec3e` normally merges main
`89757d33f61124486404bc16e84b7d3697cf2c9f` into #511. All preceding jobs had become
terminal before this update, preserving useful old-head ARM64 evidence.
The prior AMD64 failure remains a failed job: it passed PlayTime, then failed
in the old TabMaster unload-negative recovery. This merge includes #538's
shared fixture fix without retrying or weakening the negative assertion.

The exact prospective merge tree matches. Only main's checker recovery patch
and its evidence were added; the exact patch reverse-checks cleanly. All
PlayTime production inputs and private probe remain unchanged. Published
Decky 3.3.0 native AMD64 verifies 22 actual RPCs and all 28 runtime hashes.
Independent verification checks 40 published Python hashes, six SQL readbacks,
two integrity-checked SQLite snapshots, per-user isolation, paused-session
refusal, two owned stops and restart persistence. Three inventory tests pass.
The generic console flag does not certify shutdown; scoped stops are verified
separately. Raw database snapshots, consoles and verifier are retained.

Old-head ARM64/e2e/package evidence is not relabeled this head. Fresh exact
publication full CI/native matrix, e2e and applicable package gates remain
required. Automatic recording, actual Steam/session migration, official
rendered controls, real Frame and worn/controller behavior remain unverified.
No headset or schedule was touched and no release is qualified.
