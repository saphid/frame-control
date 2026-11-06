# Desktop Apps child IPC shutdown, 5 November 2026

The ARM64 native job on PR #557 at `849eb55b8f4450c3dff45e9b3adc44482dab8dae`
completed Desktop Apps' RPCs but forced SIGKILL during shutdown. The retained
artifact is `13294932523`, ZIP SHA-256
`056c19f95df391fdf5744b683d63afcb95907a031de10ac072b70759c68bd48d`.
A zero loader exit code did not qualify the failed primary case.

For store 143 Desktop Apps 0.1.0, archive SHA-256
`33fb674993c9b2bd119f0c6118c465e379f166ec1539c8183fcf7580f1d89577`,
the managed installer prepends the existing child-local EOF adapter. The original
backend, unload hook, frontend and all other archive bytes are preserved.
The parent loader and other plugins are unchanged. Existing managed copies show
an update/reinstall note when the receipt lacks `desktop-apps-ipc-eof`.

[Local input hashes and limits](framey-desktop-apps-ipc-2026-11-05.json),
[raw repaired observation](framey-desktop-apps-ipc-primary-2026-11-05.json.gz), and
[raw original negative](framey-desktop-apps-ipc-negative-2026-11-05.json.gz)
record the published digest-verified Decky 3.3.0 AMD64 loader in a cached image,
with network disabled, read-only root and private tmpfs home. No image was built.
The first trial with a 384 MiB memory cap exited before Decky's forced-stop
threshold and was excluded; the recorded primary and negative use 2 GiB and
0.5 CPU. This cached local image is supplemental evidence; hosted CI still builds
the repository's runtime image on both native architectures.

The original backend deterministically reproduced a five-second forced kill
after the fixture closed an owned Unix peer. The repaired backend served settings
after EOF and completed two parent-only SIGTERM stops, invoking the original
unload hook with zero forced kills, no exact owned descendants left, preserved
private settings and an unrelated live sibling. The new native negative restores
the exact original backend and removes only this repair. It cannot count as a
qualified primary pass. The full strict primary gate remains unchanged.

Reproduce through the repository's native runner:
`python3 scripts/framey-test-decky-runtime.py --case 143 --output /tmp/desktop-apps.json`.
It runs the repaired primary and a separate expected original-source negative.
Hosted CI/e2e and the new ARM64 shutdown probe are pending on the final PR head.
Actual Flatpak discovery, Steam shortcut mutations, app launches, real Frame,
wearer-visible UI and physical controllers remain unverified. Compatibility stays
partial; the older native functional evidence does not prove the new repair.
