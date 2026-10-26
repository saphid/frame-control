# Emuchievements ARM64 hash helper feasibility, 26 October 2026

The exact official Emuchievements 2.0.5 archive (store ID 28, SHA-256
`98dcb443e81b9f9011cfe77c69eb659869c8e2df2df8b0a443df66cbfc2f5a89`)
contains an x86_64 `Emuchievements/bin/hash`. Frame Control still blocks
that archive on ARM64; this experiment did not install the plugin.

The upstream source commit
[`8567e94befffc943434b2adb842487274815f8bb`](https://github.com/EmuDeck/Emuchievements/commit/8567e94befffc943434b2adb842487274815f8bb)
declares version 2.0.5. Its `src/py/main.py` matches the published ZIP's
`Emuchievements/main.py` byte for byte (SHA-256
`d4e72f136c94e48919575937ec4190f28864cc259eb111ef47f0df99f5912645`).
The pinned build dependencies at that commit are libarchive
`b3be94ba4f36943745e64a6a0a3c21c2d1281d3c`, libchdr
`a20e04c12c0c20048bf771da6df7aa2e51f5e0cb`, and rcheevos
`85a3209398e576d79170f569fcddf277640f3f06`.

On a separate Linux host, the version-matched source and submodules built an
x86_64 `hash` with CMake. It and the official x86_64 binary both returned
`ff78ca6c21ac11504dbddbd5d4e7524a` for one synthetic `.rom` file. An
isolated Debian cross-build using `gcc-aarch64-linux-gnu` and
`g++-aarch64-linux-gnu` produced an AArch64 binary with SHA-256
`9c7aedb80bdd64941aa5dd9b41f9bb8471411c812e04c7ee7d60486779d99997`.
It links to `liblzma.so.5`, `libstdc++.so.6`, `libgcc_s.so.1`, and `libc.so.6`.

A real Frame test acquired `/tmp/frame-test.lock` atomically with a unique
owner before reading the device. SteamVR activity was **3** (standby),
proximity raw **3.0625**, and battery **100%**. The ARM64 helper ran against
the same synthetic ROM in a private `/tmp` directory, exited 0, and returned
the same hash. The owned directory and lock were removed. No normal service,
power setting, Steam library, real ROM, or installed plugin was changed.
The separate host's source/build directory was also removed after the test.

This proves only a single-file helper path. The official ZIP remains blocked
because it still bundles x86_64 bytes. A release-ready port needs a packaged
ARM64 helper with GPL-3.0 source and license compliance, format-specific hash
coverage (including archives and CHD), a managed plugin transaction, actual
Decky backend and frontend checks, and cleanup. RetroAchievements login,
real ROM scanning, wearer-visible VR, and physical controller use remain
unverified.
