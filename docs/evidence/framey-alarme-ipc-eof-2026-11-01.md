# AlarMe child IPC shutdown repair — 2026-11-01

Tested integration `be7de42ce51924d2562be972096b97c82171cb59` stacks on
#496, base `a81bd5bf44c6d490cb9c4ccff59fdfc6a2ca8eac`. This addresses the
hidden ARM64 five-second SIGKILL found in a prior green run of #496; it does
not waive that failure. Only exact store 124 / AlarMe 1.6.3 / ZIP
`17d4166a9e98979df5fdb07c7eae42317acd54a453d3b82757508f971193c0fe`
receives the existing unchanged child IPC EOF adapter. Original backend
`ff456c2620b5b85473b4ca642551df49b490a2770e0af5c2706c6069c9f73d27`
becomes managed backend
`1bf6512c51c1693176385621c47dfe2c53a3f6d58baa2e9f4961660b3709160a`,
retaining #496's paused-restart guard. API1, published frontend/license and
other archive bytes remain unchanged; missing helper delivery refuses install.

## Verification

- Deterministic RED at `61cfeb5f36340c31be37b221a9f57e0340992a38`:
  close a real private child Unix peer, signal only the published Decky loader,
  observe parent exit zero after **5.235s**, one forced plugin kill and missing
  unload callback. The new strict gate rejects it. The earlier green parent
  result is not accepted as child-cleanup evidence.
- Native AMD64 published Decky 3.3.0 at repair
  `e44441560adadcabc8002b8899a9cf22a3d4282d`: **39 repaired / 38 original
  API1 RPCs**, all 77 responses matched. Two strict managed parent-only stops
  take **0.216s / 0.214s**, with no forced kill, shutdown error or exact surviving
  descendant; adopted exit statuses are zero and the unload callback is present.
  The first includes the actual peer disconnect. Original paused-restart and
  elapsed-deadline failures remain required negative controls. All **32 native
  source hashes** match the tested integration; backends were reconstructed
  independently from the pinned ZIP and unchanged adapter.
- Two JSON diagnostics remain in each complete native console. The scoped
  strict managed stop passes, but generic global-clean flags remain false.
  Complete independent filesystem snapshots were not taken. No broader cleanup
  or diagnostic-free claim is made.
- **133 focused tests / zero skips** cover exact delivery, preserved members,
  missing-helper refusal, receipt updates, child IPC and native inventory.
- The corrected full fake-Frame e2e passes **53 tests / zero skips**, all **116
  pins**, **69 install/removes** and **47 expected refusals**. Official backend
  execution is stubbed. Prior image tags were restored, owned containers,
  volumes and networks removed, and the shared simulator stayed healthy.
  Two HTTP listener ResourceWarnings remain; #544 addresses those separately.
- The first full e2e failed one stale expected-backend-hash assertion. Actual
  installed bytes were correct; only that assertion changed in `be7de42`.
  Its failed log, catalog and complete cleanup record remain in the raw packet.
- Whole installer/checker/e2e/store-test ASTs outside AlarMe remain unchanged
  relative to the stacked implementation. All 36 other native cases, 116 pins
  and policies, 115 other complete rows, original ZIP and IPC adapter remain.
  Another 1,766 base Git objects match; generated docs pass.

## Limits

Fresh exact-publication hosted CI, strict native ARM64 shutdown, integration
with current main, feedback and mergeability gates remain required. #496 stays
held until this repair is integrated and that combined head qualifies. This
local record does not prove the adapted backend on ARM64/Frame, sound, actual
sleep inhibition, production Steam CEF, browser or wearer/controller usability.
No headset was contacted, woken or given input. Compatibility remains partial;
existing managed installations require Update/reinstall. No release qualifies.

[Source-bound audit](framey-alarme-ipc-eof-2026-11-01.json) ·
[Raw RED, failed first e2e, GREEN and verifiers](framey-alarme-ipc-eof-2026-11-01-raw.json.gz).
