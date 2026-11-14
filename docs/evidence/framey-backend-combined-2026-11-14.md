# Combined backend qualification, 14 November 2026

PR #702 now preserves the original Bluetooth, #503 Non-Steam Badges and #511
PlayTime commits through normal merges, including main `a3c6f491`. All 42 main
cases remain in order, including both Prefix Manager versions. Badges and
PlayTime bring the primary count to 44. The independent source audit preserves
55 existing native probe bodies, 56 prior evidence files and 113 unrelated
catalog rows byte for byte. Product frontend bytes match main.

All 157 focused store, compatibility, runtime coverage and IPC tests pass.
Generated documentation matches. The actual full fake-Frame `test_framey`
module passes all three tests in 129 seconds (198 seconds with builds),
including the repaired pinned Badges install/remove assertion. The stale
expectation now checks both managed shims and exact backend/helper hashes.

Four native AMD64 published Decky 3.3.0 positives and four negative controls
pass on the frozen combined source. An independent observer verifies all 240
source bindings and complete console digests, eight positive parent-only
stops, recorded descendant identity cleanup and zero positive forced kills or
shutdown errors. Bluetooth and Badges permit RPC after controlled EOF and
restart cleanly; exact original/home-only controls reproduce the respective
forced-kill and hardcoded-home failures. AlarMe preserves paused and elapsed
paused timers; the original backend reproduces ticking and timer deletion.
PlayTime passes 22 API1 calls, six SQL readbacks, user isolation and restart
persistence; two byte-identical SQLite snapshots pass independent read-only
integrity and expected session/duration checks. The inherited Terminal candidate
also passes its native console gate, with all 72 input hashes independently
matched. Its published-plugin import blocker remains separate.

Generic global shutdown flags remain diagnostic false for scoped probes that
already stopped their own loaders. The explicit domain stop records carry the
positive cleanup proof. AlarMe's original negative lacks a full identity audit;
zero loader exits alone are not a complete negative cleanup claim. Raw reports
retain full consoles, stop records, SQLite snapshots and source bindings.

Fresh exact-head full hosted AMD64/ARM64, package and e2e checks still gate merge.
This is isolated synthetic proof: real Frame, radio/pairing, Steam-page badges,
automatic play recording, live Steam callbacks, worn UI, physical controllers,
scrolling and VR keyboard remain unverified. Compatibility stays partial.
