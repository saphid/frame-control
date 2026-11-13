# Game Theme Music private settings in published Decky, 29 October 2026

The exact official Game Theme Music 1.7.1-1 archive (store ID 52, SHA-256
`9ce293ab4db212c03c6b96dfbc5e4d92e874d33387463f53223773921f75a80e`)
was installed through Frame Control's normal managed transaction in a
disposable container. The published Decky 3.3.0 x86_64 loader (SHA-256
`e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181`)
discovered the unmodified plugin. Its instance RPC returned the requested
default for an absent private setting, saved a fixture value, read it back,
and read the same value after the loader restarted.

The probe used `scripts/framey-test-decky-runtime.py --case 52` with no network,
physical device passthrough, Steam library, or host session access. The container's home,
settings, and runtime paths were temporary; its loader, image, and container
were removed by the runner. The plugin's media search, download, playback,
and Steam game-page patch methods were not called. The focused run exited 0.
The same case is part of the hosted native Decky matrix for x86_64 and ARM64;
the local result above proves x86_64 only.

An [earlier local Chromium replay](framey-game-theme-music-2026-10-26.md)
rendered the Settings view with backend and network calls denied. This native
backend check does not prove that panel settings reach the backend in Framey.
Game Theme Music remains **partial**. Real Frame backend behavior, music
behavior, game-page integration, worn VR, and physical controllers remain
unverified.
