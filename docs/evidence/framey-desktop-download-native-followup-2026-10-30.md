# Desktop Apps and Download All native CI follow-up

The [independent artifact audit](framey-desktop-download-native-followup-2026-10-30.json)
checks exact head `6e8f0f9291be2db99862ab1e38b9e9edc1c8f745`, native Decky
workflow [41112855329](https://github.com/saphid/frame-control/actions/runs/41112855329).
Both pinned Decky 3.3.0 loaders and the exact official plugin archive digests match.
The logged checkout trees equal the entire exact head; six additional source
and fixture fingerprints bind the two case definitions and their archives.

Desktop Apps 0.1.0/store 143 passes 13 actual RPCs on AMD64 and ARM64. Private
desktop entries verify XDG precedence, nested IDs, field-code expansion,
Flatpak *metadata* parsing, and exclusion of seven invalid or hidden entries.
Favorite, hidden and last-opened settings persist through a loader restart.
Temporary-shortcut bookkeeping deduplicates, persists and removes a private
numeric ID. No application launches; no Steam shortcut is created or removed.
This does not discover an actual installed Flatpak or exercise a connected
browser panel.

Download All 1.1.0/store 131 passes discovery and its single logging RPC on both
architectures. Its backend only logs messages. The separate
[queue fixture evidence](framey-download-all-2026-10-30.md) remains synthetic
Steam/browser evidence; backend discovery does not prove real queue behavior.

Both entries remain **partial**. Their digests, status, install policy,
required shims and update requirements are unchanged. Real Steam queue or
shortcut operations, app launch, actual installed Flatpak discovery,
browser/backend integration, real Frame execution, wearer-visible content
and physical controller usability remain unverified. These results do not
satisfy release approval or locked real-Frame smoke requirements.
