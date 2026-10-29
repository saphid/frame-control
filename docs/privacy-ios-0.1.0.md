# Frame Control for iPhone and iPad — Privacy

Applies to iOS version 0.1.0, including build 202610160824. Updated 29 October 2026.

Frame Control is an independent, open-source companion for your Steam Frame. It does not require a Frame Control account. This iOS release has no advertising, tracking SDK or automatic usage-analytics system. The maintainer does not automatically receive your headset credentials, files, clipboard, screenshots or usage history.

## Connecting to your headset

With your iOS local-network permission, the app uses Bonjour to discover Steam Frame devices advertising _steamos-devkit._tcp on your network. You can also enter a headset address manually. Discovery is used to help you connect; it is not sent to the maintainer.

The app generates an SSH key and stores its private part in the iOS Keychain, restricted to that device. The public key is added to the headset you pair. Your headset address, SSH username and pinned host key are saved on your device. The Developer Mode password is used during pairing and is not saved by the app.

The app copies its bundled server to your headset and uses an SSH tunnel to communicate with it. The server listens on the headset's loopback interface and exits when the connection ends. Its cached program files may remain on your headset for later use.

## Data you choose to use

Headset status, installed-game and app lists, file information and captures travel between your device and your headset to provide the requested features. Files you send are copied to the headset. Clipboard text is used when you request the clipboard action. Saving or sharing captures uses the iOS share sheet and the destination you select; adding an image to Photos requires the corresponding iOS permission.

In this release, compatibility reports are saved on the headset and are not uploaded in the normal consumer setup. A separately configured compatibility-service key can enable a shared database; the app does not supply that key. Review any free text before deliberately sharing it.

## External services

Catalog, artwork, fonts, app-download and website links may connect to services such as Steam, F-Droid, Flathub, GitHub and sources you choose. Those services receive the network requests needed to provide their content and process them under their own privacy policies. External website links open in your system browser. Frame Control does not use those requests to track you across apps or websites.

The public Frame Control website is separate from the iOS app. Its feedback form publishes the details you submit as a GitHub issue. Do not include private information. The website's privacy notice, including its hosting and abuse-prevention details, is at https://framecontrol.fun/privacy/ . That notice also describes telemetry in later desktop releases; the desktop PostHog telemetry is not included in this iOS 0.1.0 release.

## Control and contact

You control the paired headset and the data you transfer. You can remove the app from your iPhone/iPad, remove its public key from the headset's SSH authorized keys, and remove the cached Frame Control files from the headset. Connection settings stay on the device until you change/remove them or iOS removes app data. Files, captures and local compatibility reports remain on your devices until you delete them. The maintainer has no automatic copy to retain or delete. iOS manages app permissions and Keychain storage; removing the app may leave Keychain items managed by iOS.

For private privacy questions, email saphid@gmail.com. Public support: https://framecontrol.fun/feedback/ . Avoid including secrets or other private data in public feedback.
