# Private LÖVE games on Frame

Some games contain Lua source and assets for the LÖVE engine in their extracted
RomFS. They can use LÖVE's native ARM64 Android runtime instead of NxNative's
Switch OS and graphics compatibility layers. This is a separate runtime path;
it does not make arbitrary Switch ROMs compatible with LÖVE.

`package.py` accepts your extracted game folder with `main.lua` and the official
[LÖVE 11.5a embed runtime](https://github.com/love2d/love-android/releases/tag/11.5a).
It checks the runtime's pinned SHA-256, embeds your assets, gives the app its
own package, label, provider and permission identities, and signs the result
with Frame Control's local key. Keep that key for future updates.
Use the same Frame Control app-data directory as the original build when
updating: changing `FRAME_CONTROL_DATA_DIR` selects a different signing key.

Packaging also compiles a clipboard-service fix with JDK `javac` and Android
SDK `d8`/`android.jar`. The pinned runtime remains the verified input. Lepton
can return no Android clipboard service; the original SDL handler crashes in
its constructor. The replacement skips listener registration, reports no text,
returns null on reads and ignores writes when that service is absent. Normal
clipboard behavior is retained when it is available.

```sh
python3 frame/love/package.py \
  --runtime /path/to/love-11.5-android-embed-norecording.apk \
  --game /path/to/my/extracted/RomFS \
  --output /path/to/MyGame.apk \
  --package com.example.mygame --label 'My Game' \
  --android-jar /path/to/Android/sdk/platforms/android-36/android.jar \
  --d8 /path/to/Android/sdk/build-tools/36.0.0/d8
```

In Frame Control, open **NxNative games → Preparing NxNative and LÖVE games →
Install a prepared APK → Choose a file**. Select the resulting private APK,
including one on a share mounted on your computer. You can also use **Add or
install → Choose a file** directly. The link option accepts public HTTPS APK
downloads, not private LAN URLs. The game then has its own persistent Steam
library entry and Android save data. It is not an `.nxnative.zip` bundle. Never publish the generated APK
as a Frame Control release asset: it contains your game files.

The engine and game assets are supplied by the user and stay outside this
repository. No game URLs, keys or content are included.

## Clipboard fix provenance and reproducibility

`SDLClipboardHandler.java` is an explicitly altered extract from official
`love2d/love-android` tag `11.5a`, commit
`55feb38fa144f4734c26742389f279fb07d955c0`, file
`love/src/jni/SDL2/android-project/app/src/main/java/org/libsdl/app/SDLActivity.java`.
The upstream file SHA-256 is
`88e49e925b1c89f593fcd404925a43762a194ba108c48bb5140e794c292358fd`.
The original [SDL license](LICENSE.SDL.txt) is preserved. Only null guards were
added to the extracted handler; no game assets or native libraries change.

`clipboard.py` removes that exact class definition from the checked runtime's
DEX class table, updates its map/checksums, compiles the replacement as Java 8,
then uses D8 to merge it with the remaining runtime classes for API 26 and up
(Frame's Lepton is API 30). Compile-only SDL signatures are not shipped in the
APK. Other SDL and `org.love2d.android.GameActivity` classes come from the
original runtime. Unexpected runtime layout or a missing class is rejected.

Each output has an `.apk.receipt.json` sidecar recording upstream provenance,
modified source/patcher hashes, Android platform and D8 tool hashes/versions,
DEX hashes, game payload digest, signing certificate digest and final APK hash.
Use identical source, JDK, SDK tools, game files and signing identity to reproduce
the build. JDK 21.0.13 and build-tools 36.0.0 produced identical DEX output in two
independent compiles during the Frame bring-up. The private APK and its game
payload stay outside the repository and public releases.

APK signatures use v2 for Frame. When checking these packages with the Android
SDK, use `apksigner verify --min-sdk-version 26 --print-certs MyGame.apk`;
the original runtime manifest's older minimum otherwise requests a v1 signature.

Packaging and manifest-identity tests do not establish a game's compatibility.
Verify startup, controller input, display, audio and save/reload on the physical
Frame for each game before describing that game as working.

The private Balatro build was exercised on Frame through actual remote touch
gameplay and produced nonzero audio. Continue after a cold restart, restoration
of an in-progress run, physical controller feel and worn-headset comfort remain
unverified. These observations do not establish compatibility for other LÖVE
games.
