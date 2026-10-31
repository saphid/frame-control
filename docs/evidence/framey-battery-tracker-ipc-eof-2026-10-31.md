# Battery Tracker: let pending samples flush after a child IPC disconnect

Battery Tracker 0.2.0 (store 67, archive SHA-256 `91c388d3c1b52079314045b79671ad55c767510658b6193f6936ed6cad383b94`) could pass native RPC probes yet require Decky's five-second plugin SIGKILL during unload. In the retained ARM64 console from [run 41188680065](https://github.com/saphid/frame-control/actions/runs/41188680065/job/124500753877), the managed recorder never reached its existing unload hook. A fresh isolated AMD64 replay with main 0082d79's production installer reproduced the force-kill and an empty SQLite database despite pending samples.

The exact managed archive now installs the existing child-local IPC EOF adapter. It ends only a closed peer's dispatch loop, allowing the event loop to run recorder cancellation and flush pending samples. The previous managed backend is otherwise byte-identical: removing the three adapter import/install lines restores SHA-256 `490d8334b173f956f286e50c9d01af5b83416e8e0037685366efb75c6c323241`. The shared adapter, parent loader, root-free manifest, battery selection and recorder logic are unchanged. Existing managed copies need Update/reinstall; compatibility remains partial.

## Verification

Source revision `65a22d97b5a732205d4886ab7a1d46c291de97ac`, based on main `0082d79a3ff9a9338e49dd5c83bbe25aa9e784b4`:

- 85 focused installer, compatibility, runtime-inventory and IPC tests pass. The generated compatibility document and diff checks pass.
- Fresh isolated native AMD64 uses the digest-pinned published Decky 3.3.0 loader (`e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181`). All 16 native source fingerprints independently match the tested source.
- The repaired case records 36 authenticated legacy RPCs. A deliberate connect/close of its sole private Unix peer precedes a parent-only loader stop. Two pending samples reach SQLite; a replacement loader reads that history, records another pending sample, and flushes it on a natural parent-only stop. Both loader exits and recorded adopted-child exits are zero, exact recorded descendant identities disappear, no plugin SIGKILL/shutdown error is present, and an unrelated sibling survives.
- The previous managed source is restored by hash in a separate disposable container. The same peer disconnect reproduces a five-second forced plugin kill and loss of all pending samples after 34 RPCs. This is an expected negative control, not a compatibility pass.
- Both final database snapshots are hash-checked, independently opened read-only and integrity-checked. The repaired snapshot contains the exact three synthetic rows; the prior-source snapshot has none. Raw phase consoles, hashes, owned process identities and cleanup records are retained. Generic console capture still does not assert global clean plugin shutdown.
- Every original archive member except the already adapted manifest/backend is byte-preserved. All 116 status/install policies, the other 115 complete catalog rows, the other 33 native cases and 36 other probe/setup bodies are preserved. The full hosted matrix will contain 42 probes / 34 archive pins / 16 source fingerprints per architecture.

[Independent audit](framey-battery-tracker-ipc-eof-2026-10-31.json) · [raw native reports, snapshots, complete available consoles and test output](framey-battery-tracker-ipc-eof-2026-10-31-raw.json.gz).

## Limits

This is local native AMD64 evidence. Fresh exact-head hosted checks/e2e, AMD64/ARM64 native results, every triggered package gate, current-main integration and feedback review remain required. The deliberate peer disconnect stabilizes an observed shutdown race; it does not establish its frequency in real use.

No new browser, real battery, managed Frame installation, foreground-app labeling, long-term recording, wearer-visible or physical-controller usability is proved. No headset or hourly schedule was accessed. The baseline failure report fingerprints production source but did not yet inventory the newly added helper; the final positive/prior-source replay fingerprints that helper. Other plugins' lifecycle defects remain separate work. No release is qualified or published.
