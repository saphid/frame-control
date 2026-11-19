# PlayTime current-main persistence replay, 14 November 2026

Integration `ce2bb9ba456920e7debf2f89a9c882eadc2f38a3` normally merges main
`dba4e351b3041da8a2b6d4df3fd6afb159cc47b9` into PR #511. All 40 main runtime
cases remain in order, with PlayTime added. The other 115 catalog rows and all
existing primary probe bodies are unchanged; 25 historical evidence/archive
paths retain their bytes. No production backend code changes.

The published Decky 3.3.0 AMD64 loader discovered the exact unmodified PlayTime
3.2.5 archive in a private nonroot, read-only, networkless container. The probe
passed 22 API1 calls, six SQL readbacks, paused-session refusal, two-user
isolation, and data readback after a full loader restart. Both parent-only stops
exited zero and reaped recorded descendants; all adopted child exits were zero.
Both loader consoles completed shutdown without forced kills or shutdown errors.
The generic runtime recorder's shutdown flag is false because the specialized
probe already stopped both loaders; the two explicit parent-stop observations
and complete console evidence are retained separately.

An independent audit checked all 55 source fingerprints, archive/backend and
console digests, decoded both saved SQLite snapshots through byte-identical
file-backed read-only connections, checked integrity, and confirmed the expected
300/600-second per-user rows. In-memory deserialize could not open these exact
WAL-mode snapshots; the file-backed audit did not alter their bytes. Store,
compatibility and coverage tests passed all 145 cases. Generated docs and
whitespace pass.

The first local attempt exited 143 during image build with no runtime result;
its cause is unproven and its metadata is retained. The second attempt started
only after that handle was terminal, its process/container were absent and the
other local suite had finished. This report describes that complete replay.

Fresh exact-head AMD64/ARM64 hosted qualification is still required. The catalog
remains partial. Automatic recording, live Steam callbacks, existing-user
migration, rendered UI, real Frame persistence, worn visibility, physical
controllers, scrolling and the VR keyboard are not verified here.
