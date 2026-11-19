# PlayTime private-session coverage integrated with Battery Tracker main

Tested source `252379cdb0de4d8689aeed62b3eb42816fc2c58c` normally merges prior publication `259372b967438f78d95815d7ea6dcd3a4c5ee3bc` and main
`3d6145c640ffe1f9b51923335972ddd513ad0de2`. The only conflict was generated compatibility Markdown; regenerating
it from the merged canonical data/generator retains both complete parent entries.
Whole-module AST audits preserve main's checker, runner, pin module, inventory
tests and generator outside exact PlayTime additions. All **1671
other main files**, including existing evidence, are byte-identical. Eleven
non-evidence files contain PlayTime additions; production code remains unchanged
and one catalog row updates its verification note. All **34 main native cases,
116 status/install policies, other 115 complete catalog rows and 27 native input
hashes** are preserved/verified. The audited index tree was committed unchanged.

Local Linux server: **1968 tests**, 15 platform/optional
skips. Website: **18 tests, zero skips**. Digest-verified published Decky 3.3.0
AMD64 executes **five cases across PlayTime, Battery Tracker and Steamback**;
three independent behavior/installation audits pass. This is a three-scope replay,
not a fresh whole-matrix or ARM64 execution. PlayTime verifies **22 RPCs**, all
40 original Python hashes, six SQL readbacks, two independently decoded/integrity-
checked SQLite snapshots, paused-session refusal, per-user isolation and restart
persistence with the unmodified 3.2.5 backend. Scoped stops exit zero; complete
process snapshots are not retained and global clean-shutdown flags remain false.
Battery **[38, 36] RPCs** independently verify SQLite snapshots,
pending sample flush/restart and original forced termination/lost pending samples.
Steamback **11/9 RPCs** retain private saves, undo/backup/restore snapshots,
clean unload/restart and original-negative controls. Expected negatives remain.

Isolated Fake Frame: **53 tests, zero skips**, 404.872 seconds.
All 116 exact pins and complete 69 install/remove + 47 refusal outcomes match
previous qualification. This transport suite does not execute every official
backend. Independent cleanup confirms owned resources/config/images absent while
preserving the shared simulator and pre-existing image identities. Resource
warnings remain in raw logs. The packet retains reports, snapshots, source audits,
logs and programs. Raw SHA-256: `cd240b76903fecb97d6643494df2b6b36d1ad66f86c054f50a54d12f598252b3`.

Publication adds only this note, summary and packet. Previous-head hosted
native/e2e/packages do not execute this integration. Before an ordinary push,
require all old jobs terminal, unchanged remote/current-main guards, and no main
failure; do not cancel live jobs. Require fresh exact-publication CI/e2e/native
AMD64+ARM64/every triggered package/ownership gate, exact green current-main CI,
required checks, reviews/unresolved feedback and mergeability before merging.
No merge/release is qualified by this local evidence.

Compatibility remains partial. Automatic recording, live Steam library, official
UI/actual Steam CEF, managed Frame and worn visual/controller behavior remain
unverified. Store 130 remains exactly 1.0.1; the separate GitHub 1.0.2 digest remains
lookup-unverified. Syncthing installation stays disabled. No real Frame, schedule,
PR #113, pre-existing data or security settings were changed.
