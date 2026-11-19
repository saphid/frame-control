# Notebook per-app persistence on current main

The probe ran on Linux x86_64 at the clean integrated revision `fe6ed75bab552935a72175f2684b0ed5e73dadb7`, which normally merges main `0b05d2a174da9ff84ed654de0b746e1fcdb9a178` into #497. The published, digest-pinned Decky 3.3.0 loader ran the unmodified Notebook 0.1.5 backend in a disposable container without network, host session, devices or user home access.

The [complete report](framey-notebook-main0b05-native-2026-11-14.json) records 55 source fingerprints, independent saved-file digests, default/two-app page isolation, empty pages, selection and stroke persistence across loader restart, and deletion preserving all other files. Both parent-only loader stops returned zero; the complete retained console has no forced-kill or shutdown-error marker. Report SHA-256: `bd1dfcd8e55e2715f9b7d39d2006a9b598f103154f32a2544cd63a5cde7f8d11`.

The refreshed integration also passes 28 focused runtime-coverage, official-fixture and browser-audit tests, generated documentation and whitespace checks. All 40 main runtime cases and the other 115 catalog rows remain unchanged; the 19 historical evidence files and pinned Notebook archive retain their prior bytes.

This targeted native run does not qualify the full suite, ARM64, production HTTP integration, actual Steam context/artwork, Frame rendering, worn VR or physical controllers. The earlier #497 AMD64 full-suite failure was a Bluetooth forced unload kill, not a Notebook failure; fresh hosted full-suite checks remain required. Compatibility ratings are unchanged.
