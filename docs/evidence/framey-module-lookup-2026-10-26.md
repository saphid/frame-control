# Framey-local module lookup: official plugin checks

TabMaster 2.15.1 now renders its QAM and bundled documentation in local Chromium.
Opening its docs, selecting Overview and Filters, and returning to the panel
passed. Its status moves from **broken to partial**: library editing controls
remain disabled because Steam login, live MobX reactions and library-page
patches are unavailable. This is not working library-tab customization.

The [observations](framey-module-lookup-2026-10-26.json) pin each tested official
archive and the actual Decky 3.3.0 amd64 binary. The complete current official
store was refreshed: all 116 IDs, versions and digests match the catalog.

| Plugin | Result | Remaining limitation |
| --- | --- | --- |
| TabMaster 61 | Partial: QAM and documentation navigation render | Steam library editing unavailable; ARM64 and worn VR unverified |
| Junk-Store 84 | Loading and backend-error views render without the CSS lookup crash | Actual startup/static InitActions return an execution/JSON error; extracted scripts lack executable permission; remains broken |
| SteamGridDB 36 | Module mapping is callable | Still needs Steam's LibraryContextMenu implementation; remains broken |
| DeckSP 102 | Optional UI-audio lookup succeeds | Published bundle accesses PluginManager before initialization when MobX reaction is absent; remains broken |
| Audio Loader 16 | Optional UI-audio lookup succeeds | Still requires Steam's mutable audio playback store; remains broken |

## What ran

The host exposes a finite registry of its own components and styled CSS maps,
with DFL module/export/class lookup and mapping semantics. Unknown matches return
undefined or an empty mapping. An optional audio export explicitly reports
unavailable; invoking playback throws. No Steam webpack cache, function-source
signature, audio store or library patch was manufactured.

The full exact-bundle browser pass ran with backend and network calls denied.
It completed 102 initializers and failed 14, versus 101/15 before this theme.
Initializer readiness alone does not establish rendered or useful behavior.
After integrating main’s #286/#287/#288, all 116 were retried: 103 initializers
completed and 13 failed. The additional completion is Deck Shelves from #286;
no previously completed initializer regressed.

Focused checks used actual `ui/headset.html`, React 18.3.1 and opaque
`allow-scripts` iframes. Status/installed-plugin responses were fixture-shaped,
and the private detached library snapshot from the earlier Frame SSH check was
replayed. The relay allowed only TabMaster log/settings reads and Junk-Store's
static `init/InitActions` action. TabMaster's official backend returned the
default setting, empty users dictionary and empty tags. Junk-Store returned a
structured Type Error, which its panel displayed. RSS/network, login, installs,
launch actions and other backend methods were denied.

The unmodified Python backends ran in actual Decky 3.3.0 inside a disposable
unprivileged amd64 container with no network, host audio, devices or user-data
mounts. This bypasses Steam CEF and is not a headset HTTP/RPC check. The normal
headset lock was briefly acquired and released for read-only dependency/service
availability; no official plugin ran there in this theme. No ARM64 or worn-VR
result is claimed.

## Regression checks

- 1,621 server tests passed, 16 skipped; all 43 focused Framey tests passed
  after integrating the latest main.
- Both site test files passed.
- All 116 exact archives passed the fake-Frame audit: 60 install/remove flows
  and 56 expected blockers. Official backend execution remained stubbed.
- The unique fake-Frame project and its volumes were removed. The focused
  backend container and both loopback helpers were removed after the checks.

The catalog and generated compatibility table use the same status/reasons as
both store views. The result is **1 works / 50 partial / 54 broken / 11 N/A** (including main’s independent Deck Shelves improvement);
the majority goal remains open.
