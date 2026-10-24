# Frame Control for Android phones

The native Android companion lives in `android/`. It requires Android 10 or
later and a Steam Frame with Developer Mode and SSH enabled. This is a new
implementation, separate from the headset's `frame/android` Lepton tools.

## Pair and sync

1. Enter the headset address, SSH port and username (normally `steamos`).
2. Choose **Pair headset**, compare the displayed SSH fingerprint with the
   headset's identity, and accept it. Enter the Developer Mode password once.
   The app installs this phone's SSH public key and verifies key login before
   storing the pairing. The private key stays in Android Keystore; the
   password is not saved. A changed headset host key is refused.
3. Choose **Start syncing** and allow notifications. The persistent notification
   shows the active connected-device session and offers **Stop syncing**.
4. Take a new screenshot. Its original downloads into Frame Control. **Save
   screenshots to Gallery** is enabled by default and adds it to
   `Pictures/Frame Control`. Android 10+ lets an app create its own Gallery
   items without broad photo-reading permission.

The first successful listing establishes a history baseline. Existing screenshots
are not imported automatically. The app waits for two equal size/time listings,
checks the original's byte count and image decode, and saves it atomically.
Identity includes the paired headset, Steam account, game and filename.

Turning Gallery off keeps automatic downloads inside Frame Control. Pending
exports become app-only; enabling it again does not export those earlier items.
Previously saved Gallery items stay there. Original files remain available from
**Open / share original** when disconnected. The app keeps each headset's
library separately.

Gallery export uses a deterministic app-owned MediaStore row. A pending row is
rewritten after interruption, and a completed row is recognized before inserting
another. A failed export leaves the app original available for retry. Preferences
and the final Gallery commit are serialized so a disabled setting is respected.

**Headset controls** opens the shared Frame Control web interface through a
loopback-only SSH tunnel. The server has a fresh session key and listens only on
the headset's loopback interface. The tunnel and server end with the phone's
SSH session. This initial Android shell does not implement all iPhone-specific
web bridges; native screenshot originals use the downloads screen.

## Background behavior and release boundary

Sync is an explicit, user-started Android `connectedDevice` foreground service.
It can continue after leaving the app while its notification is present and
reconnects when the headset returns. It is not a Firebase push receiver.
Android battery-saving/Doze, loss of network, force-stop or process termination
can delay or end the session. The app does not request battery-optimization
exemption, use unrelated background modes, or restart itself after force-stop.
Restart sync from the app if the session ends.

The full cross-platform request still requires actual locked-phone background
proof. iOS APNs delivery is a separate unimplemented dependency. An emulator
test is not evidence that either physical platform meets that requirement.
Do not publish this as a verified always-on screenshot feature.

## Build and verify

Use JDK 17 and an Android SDK containing platform 36/build-tools 36.0.0:

```sh
export JAVA_HOME=/path/to/jdk17
export ANDROID_HOME=/path/to/android-sdk
./android/gradlew -p android assembleDebug testDebugUnitTest lintDebug
```

The Gradle wrapper pins version 9.4.1 and its distribution checksum. The build
generates the same reproducible headset bundle as iOS, including the existing
SHA-256-checked KDE Connect package fetch. Generated assets and build outputs
are ignored. No signing key, headset password or machine-specific SDK path is
committed. `assembleDebug` produces `android/app/build/outputs/apk/debug/app-debug.apk`.
It uses a development signing identity, not a configured Play release key.

`assembleDebugAndroidTest` builds instrumentation for real MediaStore round-trip,
retry recovery and app-only behavior. Optional real-headset hooks exist only in
the separate test APK (`ScreenshotDeviceTest`), not in the product app. They
provision a public test key and permit original/Gallery hash readback without
adding a product authentication bypass. Remove the temporary headset key and
fixtures after live tests.

No Play app creation, store upload, invitation or public release is part of a
debug build. Preserve a dedicated release signing identity and verify physical
devices before a production release.
