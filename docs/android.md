# Frame Control for Android

The Android phone and tablet app does what the iPhone app does
([iphone.md](iphone.md)), from an Android device: headset view and live video,
battery and status, screenshots, Steam games, Android apps and their display
settings, sideloading, files, clipboard, Flatpaks, and power. Source:
[`android/`](../android).

## How it works

It works the same way as the iPhone app:

1. it connects to the Frame over SSH itself, using [JSch](https://github.com/mwiede/jsch)
   (`com.github.mwiede:jsch`, with Bouncy Castle for Ed25519, Curve25519 and
   ML-KEM). It logs in with its own ECDSA P-256 key, which is made inside the Android Keystore
   (StrongBox when the phone has one). The private key can't leave the Keystore;
   JSch only ever gets signatures;
2. it copies Frame Control's server and helpers to
   `~/.cache/frame-control/<version>` on the Frame, once per version. This is
   the same archive the iPhone build makes (see [The headset server](#the-headset-server));
3. it starts `ui/server.py` there with `FRAME_LOCAL=1`. The server listens only on
   the Frame's own 127.0.0.1, and it stops when the session ends (`--exit-on-eof`);
4. it forwards a port on the phone's 127.0.0.1 to it through the SSH session (`ssh -L`), and
   shows the page in a web view. The page carries a fresh 192-bit key each
   session, which the server requires on every API request.

The web view loads only that tunnel's exact origin (`http://127.0.0.1:<port>`).
Web links open in the system browser, and only when tapped. Other local ports,
`file:`, `content:`, `intent:`, `javascript:` and `data:` don't load at all
(`core/OriginPolicy.kt`). The page's `window.frameApp` bridge (clipboard, Save,
other apps, install links) is injected only into that origin, through
androidx.webkit's origin-checked `addWebMessageListener`. There is no
`addJavascriptInterface` object.
External image/font requests from the pinned page are intercepted, restricted to
an explicit HTTPS asset-path allowlist, and fetched by the headset through SSH.
Redirects and response type/size are checked. The phone never fetches CDN assets
directly. Other network subresources are blocked; local screenshot blobs still
render. See `core/RemoteAsset.kt` and `WebShell.Client`.
Plain HTTP is allowed only to `127.0.0.1` (`res/xml/network_security_config.xml`).

The app stays connected while it's in front, and for three minutes after it
goes out of sight. Android or the network may end the connection sooner. After
three minutes the app disconnects, which stops the server on the Frame, and it
reconnects when you come back. While connected it checks the session every 20 s.
A dropped connection is restarted, and the page reconnects. A Frame that isn't
answering gets the "Waiting for your Frame" screen, which retries by itself.
System document pickers temporarily put another Activity in front. A local,
unexported connected-device foreground service keeps the headset connection
running during the picker, for at most three minutes; it stops on result,
cancellation or Activity destruction and never restarts itself. It posts a low
importance notification with a return-to-app action. On Android 13 and later,
without notification permission this service appears in the system's Active apps
list rather than the notification shade. The app does not ask for notification
permission. If a connection or renderer is lost anyway, the old file callback
is cancelled and a later selection asks the user to choose files again instead of
silently delivering it to a destroyed page. Loaded game covers hide the pinned
page's opaque fallback with a scoped Android CSS rule.

## Pairing

On the Frame, turn on Developer Mode and set a user password: Steam Settings →
System → Enable Developer Mode, then Developer → Set User Password. In the app,
wake the Frame. The app looks for Valve's `_steamos-devkit._tcp` service and probes
`frame.local`, or the address you type, with an optional port and user. Then enter
that password once.

Before anything is sent, a password included, the app shows the Frame's SSH
host key fingerprint (`SHA256:…`, as `ssh-keygen -lf` prints it). It also tells you how
to check it on the Frame. Only **Trust and continue** lets the connection go on.
The app then adds its key to `~/.ssh/authorized_keys` and saves the address and
that host key. It never saves the password.

On later connections, only that exact host key is accepted. If it changes, the
app refuses to connect and asks you to pair again. It never offers to accept the
new key.
Pairing again, after you choose **Forget**, shows the new fingerprint with a warning
that it differs from the one trusted before.

If you already reach the Frame over SSH, **Already reach the Frame over SSH?**
shows this device's public key to add yourself, and connects without a
password. The fingerprint is still confirmed on that first connection.

To revoke a phone, remove its line (`frame-control@android-<model>`) from
`~/.ssh/authorized_keys` on the Frame.

## What's different from the iPhone

| iPhone | Android |
|---|---|
| Save opens the share sheet | Save puts images in Pictures/Frame Control, one at a time in bounded chunks (MediaStore, no storage permission) |
| General file downloads | Android Create Document picker; authenticated tunnel streams or chunked blob transfers, maximum 2 GiB |
| Send to Frame picks from Files | Send to Frame uses the system file picker; you pick each file, and folders need zipping |
| SSH, SFTP open Blink Shell or Termius | They open any app that handles `ssh://` / `sftp://`, or Google Play |
| Host key recorded on first connection | Host key confirmed by you on first connection |
| ed25519 key in the Keychain | ECDSA P-256 key in the Android Keystore |

Back steps through the page's tabs, then leaves the app. Rotation, split screen,
tablets and foldables keep the same session, because the activity handles
configuration changes itself. A crashed page renderer gets a fresh web view on the
same tunnel.

## The headset server

The app carries the server's `.tar.gz` as the asset `frame-bundle.bin`. The name
avoids `.gz`, because asset packaging would unzip the file, and the app checks
the asset's SHA-256 against its version before using it.
`android/scripts/frame_bundle.py` makes it
from a `git archive` of one pinned commit, so uncommitted or untracked files
can't get in. It packs the archive with that commit's own
`ios/scripts/make_frame_bundle.py`, so the archive is byte for byte what the iPhone build
makes from a clean checkout. `android/gradle.properties` pins the commit
(`frameControl.bundleRev`) and the archive's SHA-256 (`frameControl.bundleSha256`).
The build fails if the archive differs.

The pinned commit is `3fdc6c46c3ea4205c7b22a496c053cf4d2674596`, which gives
archive `7e89a36e…`, version `7e89a36ea905297f`. It is **not** the archive in
iPhone TestFlight build 202610140516 (`df6ac51f…`, the build later uploads
reuse). That archive was packed from a working tree with uncommitted changes:

- it has six files that were never committed: `scripts/environments.sh`,
  `scripts/store-on-frame.sh`, `scripts/uuvr-on-frame.sh`, `ui/environments.html`,
  `ui/frame_uuvr.py` and `ui/store.html`;
- it has uncommitted edits to `ui/server.py`, `ui/index.html` and `ui/frame_host.py`.

No commit reproduces it. Until those changes are committed, the Android app has
the committed server: no Environments, Store or UUVR pages.
To move the app to a later server, commit it, then change both pinned values together.

## Building

Needs JDK 17+, the Android SDK (platform 36, build-tools 36.0.0) and Python 3.8+
with `git` (for the bundle). Gradle comes from the wrapper (9.8.2,
distribution and wrapper checksums pinned). Every dependency's SHA-256 is in
`gradle/verification-metadata.xml`.

```sh
cd android
export ANDROID_HOME=/path/to/sdk
./gradlew assembleDebug          # app/build/outputs/apk/debug/app-debug.apk
./gradlew testDebugUnitTest      # needs python3: runs the real server in tests
./gradlew lintDebug
./gradlew bundleRelease          # app/build/outputs/bundle/release/app-release.aab, unsigned
```

The bundle is built from the repository's Git objects. To build without the
repository, pass a copy that matches the pinned hash:
`-PframeBundleArchive=/path/frame-bundle.tar.gz`.

The release bundle is unsigned. The release key is applied after review, outside
this build. The debug build installs as `com.saphid.framecontrol.debug`, next to
the release build, with its own key and pairing.

## Tests

`app/src/test` runs on the JVM. `TestHeadset` is a real SSH server (Apache MINA
SSHD) on 127.0.0.1. It runs commands in a temporary home directory, serves SFTP
and allows `ssh -L`, and it counts every login attempt. Against it, the
tests check that:

- the fingerprint shown is the server's own, as MINA computes it, and no password is
  offered until it's confirmed;
- declining sends nothing and saves nothing;
- a changed host key is refused, without a question and without any login;
- cancelling mid-question closes the session;
- the bundled `ui/server.py` really starts, and serves the page and key-checked
  API through the tunnel;
- the server stops by itself when the app leaves, through end of input;
- a dropped connection reconnects;
- a server that dies at once is reported instead of restarted forever;
- an absent Frame is retried until it's back;
- a wrong password asks to pair again.

Regressions also exercise teardown after the work scope is already cancelled,
password wiping when a coroutine never starts, authenticated download redirects,
chunk order/size/integrity and interrupted-save cleanup. `node
android/scripts/test_bridge.mjs` checks the actual injected bridge with a 51-image
library, partial failure at image 22 and a multi-chunk blob download.

Smaller tests cover the origin/asset policies, install links, address parsing and
host key ordering.

## Google Play

Play requires new apps and updates to target API 36 from 31 Aug 2026
([target API requirements](https://developer.android.com/google/play/requirements/target-sdk)).
The app targets 36 and compiles against 36, with minSdk 29 (Android 10).
Targeting 37 will need the local-network permission (`ACCESS_LOCAL_NETWORK`)
asked for at runtime, because Android 17 blocks LAN access for apps that target it
([local network permission](https://developer.android.com/privacy-and-security/local-network-permission)).
Data safety answers are in [privacy-android.md](privacy-android.md).


### Foreground-service declaration (draft)

Declare the `connectedDevice` foreground-service use in Play Console. The user
starts Send to Frame or chooses a save destination. The service preserves the
existing SSH connection to their external Steam Frame while Android's document
picker is in front, posts its notification (shown in Active apps rather than the
notification shade without notification permission on Android 13+), and stops when the picker returns
(or the Activity is destroyed, or the three-minute ceiling is reached). It has
no boot receiver and does not restart. `CHANGE_NETWORK_STATE` is Android's normal
permission prerequisite for this network-connected-device type; the app does not
use it to alter network settings. See [Android's connected-device service
requirements](https://developer.android.com/develop/background-work/services/fgs/service-types#connected-device).
Use genuine long-picker runtime footage for Play's service-use demonstration;
this draft has not been submitted.
