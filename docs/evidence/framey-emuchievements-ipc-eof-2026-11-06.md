# Emuchievements child IPC shutdown repair, 6 November 2026

PR #573’s native ARM64 Decky check rejected Emuchievements 2.0.5 because the loader forced the child to stop after five seconds. The parent returned zero; the strict shutdown gate correctly rejected the hidden child failure.

The installer now gives only the exact pinned managed archive the existing plugin-local child IPC EOF adapter. It preserves the verified managed Python body, hash helper, public RPCs and original unload hook. Existing copies need update or reinstall. The required receipt includes both `emuchievements-safe-arm64` and `emuchievements-ipc-eof`.

In native x86_64, isolated Decky 3.3.0 containers, synthetic direct/ZIP hashes, literal paths and hostile archive refusals pass. Hash RPCs still work after an actual Unix peer disconnect. Two parent-only shutdowns complete below five seconds without forced kills, execute the original unload hook, reap the recorded children and preserve an unrelated sibling. Restart preserves the exact private settings bytes and hashing still works.

The negative control removes only the IPC prefix/adapter and restores the exact prior managed source. It reproduces one forced plugin kill and no clean-shutdown claim. The new ARM64 candidate still requires CI; this local test makes no ARM64, real-ROM, account, Steam UI, Frame, controller or worn-VR claim.

Installer tests: 84 passed. Compatibility tests: 26 passed. The shared IPC tests pass 4/4. The fake-Frame pinned-official install/remove test passed, including the delivered managed-source hash, adapter hash and both receipt shims. The full native suite is a separate check; consult its run result.

[Machine receipt](framey-emuchievements-ipc-eof-2026-11-06.json) and [raw isolated receipt](framey-emuchievements-ipc-eof-2026-11-06-raw.json.gz).
