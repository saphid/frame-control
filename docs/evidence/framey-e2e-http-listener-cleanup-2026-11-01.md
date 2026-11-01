# Close simulator HTTP fixture listeners — 2026-11-01

Implementation `fae3584abd4b9ed1a6da047df49631bb5f4bf8a3` is based on main `ad070b731386dfbc2c8ed24b901b0b5edaeacbf2`. Full simulator runs emitted
unclosed-listening-socket ResourceWarnings because the Framey store fixture and
the local title-manifest fixture called `shutdown()` without `server_close()`.
`shutdown()` stops the serving loop; it does not close the listener.

Two source lines register the existing close method with unittest's class/test
cleanup hooks. Normal teardown first shuts down serving, then the cleanup closes
the socket. Every other **1750 main Git object** is unchanged; all **31
native Decky inputs** match main byte-for-byte. No production code, catalog pin,
classification, installation policy or real headset state changed.

## Verification

The full disposable fake-Frame suite passed **53 tests / zero skips** in
**411.758 seconds**, with **zero ResourceWarnings observed**. The previous
local run at `b96c5a3ae3550b7470d4aad45bc79ccaf07089eb` emitted **two unclosed socket warnings**; both original
fixture files in that run are byte-identical to main. This is a local AMD64
comparison, not fresh hosted ARM64 qualification.

The catalog audit covers **116 exact archive pins**, **69 install/removes** and
**47 expected refusals**, with every result identical to the prior local full
catalog run. Official backend execution remains stubbed in this simulator;
this change makes no plugin/native/VR compatibility claim. Owned Compose
containers, volumes and networks are gone, and the pre-existing shared
simulator remains healthy. Source and diff checks pass. The raw packet
retains before/after logs, complete catalog observations, input fingerprints
and the verifier.

Fresh exact-publication hosted CI/e2e and every triggered gate remain required,
with exact current-main green, mergeability and unresolved-feedback review.
Native Decky was not rerun for these two test-only cleanup lines. No Frame,
wearer/controller, merge or release qualification is claimed.

[Summary](framey-e2e-http-listener-cleanup-2026-11-01.json) · [Raw logs and verifier](framey-e2e-http-listener-cleanup-2026-11-01-raw.json.gz).
