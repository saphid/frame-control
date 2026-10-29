# Game Theme Music settings panel replay, 29 October 2026

The exact official Game Theme Music 1.7.1-1 ZIP (store ID 52, SHA-256
`9ce293ab4db212c03c6b96dfbc5e4d92e874d33387463f53223773921f75a80e`)
ran in Framey's opaque local Chromium panel. The audit's opt-in
`--theme-music-settings-fixture` admitted only positional `get_setting` and
`set_setting` calls for a bounded, in-memory `settings` object. The page CSP
and fetch override blocked network access; media, cache, and Steam-page backend
methods had no fixture replies. No official backend ran in this browser check.

The initializer completed and the Settings view rendered. A `get_setting`
request read the default object. Clicking **Default Muted** saved `true` through
Framey's panel message transport. Entering **40** in the Music Volume numeric
control saved `volume: 0.4`. Reloading the iframe read the in-memory value and
rendered the checkbox checked and both volume controls at **40**. Clicking
**Use yt-dlp** then saved `useYtDlp: true` and `downloadAudio: true` through
two official frontend calls. The fixture's contract test also rejects other
methods, legacy calls, wrong keys, and out-of-range settings.

A [separate published Decky 3.3.0 check](framey-game-theme-music-native-2026-10-29.md)
proved private setting storage across a loader restart in an isolated x86_64
container. These are separate checks; the Chromium panel did not connect to
that native backend. Music search, downloads, playback, Steam game-page
injection, real Frame behavior, worn VR, and physical controllers remain
unverified. The compatibility label remains **partial**.
