# ProtonDB original-source negative: repeated forced-stop warnings

PR #529 head `182803cea0a13ff3ff9a70d19fc0a4e00f9dcd6c` failed native AMD64
job `124592953800` and ARM64 job `124592953881` in the deliberate original-source
shutdown negative. Each exact failure observation records two forced-stop warning
entries, a failed clean-shutdown verdict, loader exit zero, no remaining owned
identities and adopted child exits zero. An outstanding `get_system_info` RPC
also reports `PluginStopped` during loader shutdown. The test required exactly
one warning and rejected these reproduced negatives.

The corrected negative assertion requires at least one forced-stop warning,
keeps its raw count, rejects a clean/unload-completed verdict, and additionally
requires no remaining owned identities, no shutdown error markers and successful
loader/adopted-child exits. It does not alter positive clean-stop qualification,
the shared stop helper, EOF adapter, installer, catalog or any production file.
Warning entries do not identify distinct killed processes; no such count is
inferred from the two repeated messages.

Two unit tests exercise one/two warnings without mutating the observation and
reject missing forced-stop evidence, a clean verdict, failed loader/child exits,
live descendants, errors and unload completion. Both actual hosted failure
observations independently pass the corrected negative assertion. They remain
recorded failures of the earlier test head, not successful CI runs.

A fresh isolated published Decky 3.3.0 AMD64 run reproduces the two-warning
original-source negative. The repaired backend still passes ten RPCs, answers
after EOF, retains private settings across two loader stops/restart and stops
cleanly in 0.185/0.185 seconds with **zero** forced-stop warnings. The original
negative retains six RPCs, a post-EOF RPC timeout and a forced stop; its verdict
remains false. Disk snapshot hashes, exact native source hashes, console hashes,
owned identity cleanup and unrelated sibling preservation are independently
checked.

[Audit](framey-protondb-negative-stop-warnings-2026-10-31.json).
[Raw hosted failures and local native control](framey-protondb-negative-stop-warnings-2026-10-31-raw.json.gz).

This correction is prepared locally while other original-head hosted jobs remain
live. They must finish before its ordinary push; a fresh exact-head hosted matrix
is then required. No new full local suite, ARM64 positive rerun, browser, badge
rendering, real Frame, wearer/controller or release proof is claimed. These
controlled EOF results do not establish the cause of earlier intermittent ARM64
socket failures. No headset or hourly schedule was touched.
