# Native plugin packaging blockers, 26 October 2026

This is a static, digest-scoped follow-up. Neither plugin was installed or
run on the Frame. Their compatibility statuses remain **broken**.

## Decky Cloud Save 1.4.2, store ID 49

The official ZIP SHA-256 is
`b311d967ddf1b0f0046d36929645855891a40173e3a93f6f0cd8b1576b04b411`.
It was downloaded and hash-checked without executing any member. Of its 27
members, `decky-cloud-save/bin/rclone` is a regular executable of **60,776,600
bytes** with ELF machine **62 (x86_64)**. The installer permits at most 30 MiB
per member, so this exact ZIP fails before native architecture validation.
Raising that limit alone would still leave an x86_64 executable on the ARM64
Frame. No cloud credentials, saves, reads or writes were exercised.

## Emuchievements 2.0.5, store ID 28

The official ZIP SHA-256 is
`98dcb443e81b9f9011cfe77c69eb659869c8e2df2df8b0a443df66cbfc2f5a89`.
The [earlier helper check](framey-emuchievements-arm-2026-10-26.md) proved
one synthetic ROM hash on ARM64, without installing the plugin. The upstream
source commit `8567e94befffc943434b2adb842487274815f8bb` and its pinned
libarchive, libchdr and rcheevos submodules were checked out separately for
this audit. The source is GPL-3.0. An isolated Debian ARM64 cross-build made a
2.6 MB helper (`c8794558a0d75294930f969a426e7d2ac13a27e3c1ff9bd8aae093e31596b9bd`),
but it was **not shipped or run on ROM archives**. A complete source bundle
without Git metadata compressed to about 8 MB; source and license distribution
would be part of any release-ready port.

The proposed source has an additional blocker. `backend/src/util.cpp` builds
an extraction destination by appending each raw archive member pathname to
an owned `/tmp/tmpdir.*` prefix, then passes it to libarchive's disk writer.
It neither rejects `..`/absolute paths nor enables libarchive's secure path
flags. `backend/src/main.cpp` later removes the extracted file's parent path.
With an untrusted archive, those paths may leave the intended temporary
directory. The plugin's Python backend also invokes `bin/hash` through a
shell with a path argument. A port needs bounded path validation, secure
extraction/cleanup, safe subprocess arguments, format coverage and actual
Decky/backend tests before its official ZIP can be transformed or installed.

The official archive still contains an x86_64 helper. RetroAchievements
login, real ROM scanning, a packaged ARM64 backend, wearer-visible VR and
physical controller use remain unverified.
