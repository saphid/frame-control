# Frame Control for Android phones

The Android app is a phone shell for the same Frame-hosted web page as the iOS
and desktop apps. Its build packs `ui/` and the headset helpers with
`ios/scripts/make_frame_bundle.py`. After pairing, it copies that archive to
`~/.cache/frame-control/<bundle hash>` on the Frame, starts `ui/server.py` there,
and shows it through an SSH tunnel bound to the phone's 127.0.0.1. Games,
Steam search, filters, details, and trailers therefore use the shared page.

## Build and test

Install JDK 17 and the Android 16 SDK (API 36), then run from the repository
root:

```sh
android/gradlew -p android assembleDebug testDebugUnitTest
```

The build downloads the pinned KDE Connect payloads if they are not cached,
then packs the same Frame bundle as iOS. The debug APK is at
`android/app/build/outputs/apk/debug/app-debug.apk`. The
`android-checks.yml` workflow builds it and retains the APK as an artifact.

On first use, enter the Frame's address, `steamos` user, and Developer Mode
password. Confirm its SSH host-key SHA-256 fingerprint against a trusted view
of the Frame. The password is used once to add the phone's public key to
`~/.ssh/authorized_keys` and is not saved. Future sessions use a per-install
RSA 3072 key; its private bytes are encrypted with Android Keystore AES-GCM.
If a trusted computer already reaches the Frame over SSH, tap **Or add this
phone's key yourself**, copy the displayed public key into that same file,
then leave the password blank and tap **Connect**. The private key never leaves
this phone.
The app refuses a changed host key until the pairing is explicitly forgotten.
Android backup is disabled for this app. The WebView bridge accepts only
main-frame messages from the current loopback tunnel origin. Cleartext HTTP
is permitted only for 127.0.0.1; SSH protects traffic to the Frame.

The app supports the shared page, file picking, clipboard, image saving,
local notifications, and opening companion apps. It requires Android 10 or
later and a System WebView with document-start scripts and origin-scoped
message listeners. The first beta still needs a physical Android phone and
Frame test of pairing, file transfer, trailers, network changes, and process
cleanup. Android does not yet discover the Frame over Bonjour; enter its
address. Install links and some native desktop-only integrations are not
exposed by the phone bridge.

## Google Play internal beta

An existing Play Console app and publisher service account are required.
Configure these GitHub Actions secrets on this repository:

| Secret | Value |
| --- | --- |
| `ANDROID_KEYSTORE_BASE64` | Base64 of the Play upload `.jks` keystore |
| `ANDROID_KEYSTORE_PASSWORD` | Keystore password |
| `ANDROID_KEY_ALIAS` | Upload-key alias |
| `ANDROID_KEY_PASSWORD` | Upload-key password |
| `ANDROID_PLAY_SERVICE_ACCOUNT_JSON` | Service-account JSON with Release Manager permission for the app |

Run `Android internal beta` (`android-beta.yml`) manually with the existing
Play package name, a new integer version code, and a version name. It builds
a signed AAB, retains it as a workflow artifact, then uploads that exact AAB
to the app's `internal` track through the Android Publisher API. No release
credentials are stored in this checkout. Keep the upload key backed up outside
the repository. This workflow cannot create a new Play Console app listing.
