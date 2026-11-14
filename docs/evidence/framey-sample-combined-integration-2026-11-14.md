# Sample persistence on repaired backend source, 14 November 2026

PR #698 normally includes #702 `9948d162` and main `98775cd2`. All seven
original sample paths retain their bytes; no other paths differ from the
combined base. #702 still needs its own accepted merge and qualification.
All 60 source bindings from the repaired Bluetooth positive/negative replay
match this refreshed source exactly. The earlier failing full-native job and
its complete failed log remain retained in the compressed report; that failure
is not erased or counted as a pass. Fresh full hosted native CI must qualify
the refreshed head.

All 52 sample/panel tests pass. The fresh native AMD64 published Decky 3.3.0
sample probe passes 18 real API2 RPC records, including 12 refused bad argument,
damaged or future-schema operations. Three settings snapshot hashes independently
match the exact expected saved JSON and 0600 mode, across two full loader
restarts. The observer verifies every one of 19 input hashes, independently
repacks the deterministic archive and checks three parent-only stop records,
console digests, zero recorded remaining descendants and zero forced cleanup.
An unrelated sibling survives every stop. Complete source-bound raw evidence
retains the transcript, snapshots, stops and console.

Fresh exact-head full hosted AMD64/ARM64 and package/e2e gates still apply. This
is isolated backend persistence proof. Browser/backend integration, real Frame
persistence, worn UI, physical controllers, scrolling and VR keyboard remain
unverified. Production sample plugin bytes are unchanged.
