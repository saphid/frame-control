# AutoSuspend and CheatDeck static action limits, 28 October 2026

This is a read-only follow-up to the exact official Decky compatibility
catalog. The two archives were downloaded from the official version CDN and
SHA-256 checked before inspection. Neither plugin was imported, installed,
opened in a live panel, or run on the Frame.

## AutoSuspend 2.2.0, store ID 27

Archive SHA-256:
`20ceb9aa5327226326531d947e4a7a5318ba78b73f503266996a81877cffa536`.
The Python backend exposes settings reads and writes. The frontend contains a
`SteamClient.System.ShutdownPC()` call and Steam suspend callbacks. Its existing
opaque Chromium audit fails during initialization with `Cannot read properties
of null (reading '6')`. Static presence of those actions does not prove that
opening the panel would call them, but a settings-only initialization check
would not establish safe threshold or suspend behavior on Frame. The plugin
remains **broken**; no suspend, shutdown, notification, or live setting was
exercised.

## CheatDeck 1.1.6, store ID 76

Archive SHA-256:
`6dfe1f821b0cfe2a61c95e49efd6cb2587d79ff3d1e101e14fa80c12c7f6d89f`.
The published README directs users to a Steam game context-menu item to choose
a trainer and save launch options. The frontend references
`SteamClient.Apps.SetAppLaunchOptions`; the Python backend provides settings
RPCs. The existing opaque Chromium audit fails with `Cannot convert undefined
or null to object`. The isolated Framey panel has no Steam game context-menu
target, so repairing that initializer alone would not verify the advertised
trainer workflow. The plugin remains **broken**; no launch-option write, game,
trainer, real headset, or worn-VR action was exercised.

These observations only refine the reasons for the two existing catalog rows.
The exact-version totals stay **6 works / 52 partial / 47 broken / 11 N/A**.
