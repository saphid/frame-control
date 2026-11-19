# Native sample settings, 14 November 2026

The exact shipped Framey Settings Sample archive passed through the digest-pinned
published Decky 3.3.0 AMD64 loader in a private nonroot, read-only, networkless
container. No backend shim or sample implementation was changed.

Real RPCs saved true, restarted the loader and read true, then saved false,
restarted again and read false with an opposite true default. Missing-state reads
did not create a file. Saved files retained mode 0600. Twelve invalid RPC calls
were refused; malformed JSON, future schema and nonboolean values retained their
original bytes after read and save attempts.

All three stops signalled only the loader parent, exited zero, reaped recorded
descendants, and logged exactly one completed unload and shutdown. No forced
fixture kill was needed. An unrelated private process survived every stop.
The JSON summary records 19 independently checked source hashes, the deterministic
archive digest and the compressed raw report digest. Raw evidence includes RPC
responses, full console text, process identities and shutdown observations.
The existing sample unit and local browser suite also passed all 14 tests.

ARM64 CI is added but has not yet passed at this evidence point. This does not
verify real Steam CEF, Frame installation or persistence, worn visibility,
physical controllers, scrolling or the VR keyboard. The sample logs that it has
no optional `_unload` method; the observed clean shutdown still passed.
