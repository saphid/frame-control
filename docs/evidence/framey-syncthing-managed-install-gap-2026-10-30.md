# Syncthing managed installation gap, 30 October 2026

Syncthing 0.2.7 remains broken and blocked from managed installation. The
candidate runtime probes stage their own backend, frontend and receipt inside
a disposable VM. They do not run the production managed installer. The store
currently declares `SYNCTHING_DIGEST` but has no adaptation recipe.

The official archive was re-read locally and matches SHA-256
`27e47379c280c92253d5533435f57c33b332b215f866d2ac4493daf18ec0d1c4`.
Its folder is `decky-syncthing`, version is `0.2.7`, flags are `debug` and its
manifest uses the legacy API. Published component SHA-256 values are:

- Frontend: `c8845ea59c4176e686b1abf9fedb1336a4e5ac26947b3db2732d926d3fc33fb4`.
- Python: `87620c3f85a381aa12d2dbee39da3629403e68c2f3ba7294b3693c2cb78e4100`.
- Original x86_64 helper: `64841dc46b07385297d630b5274596b943df0c6d8c3dd27fd74391b370577ab4`.

The next installation layer must admit only that archive and verify those
components before replacing them with the source-bound candidate frontend,
managed Python and source-built native helper. The changed helper needs actual
AMD64 and ARM64 runtime gates; cross compilation alone is insufficient.
No security or root permission change is needed.

Acceptance requires production install, update and remove through actual
Decky 3.3.0 discovery/RPC. Test fresh and legacy profiles, preserve unrelated
units/helpers and all pre-existing configuration, keys, certificates and sync
data, and remove only owned receipts, files, units and processes. Exercise
interrupted/failed staging and digest/source mismatch refusal before claiming
managed lifecycle support. Preserve the existing unit ownership and external
service refusal cases.

The exact signed application/runtime fixtures supply runtime verification, but
the installer must also report missing external prerequisites honestly. A
synthetic receipt, sandboxed desktop capture, DOM input or backend registration
does not establish managed installation, Steam CEF, wearer-visible visuals or
physical-controller usability. The separate hourly headset schedule remains
responsible for the physical gate.

A read-only replay of production `archive_info()` against those actual ZIP
bytes rejects the original x86_64 watchdog with the expected non-ARM64
binary error. The catalogue entry still has `blockInstall: true`. The
companion JSON binds both checks to the exact store/catalogue source hashes;
no installation, network operation or real Frame access was performed.
