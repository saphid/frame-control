# Frame Control for Android: privacy

This is a draft for review. It has not been published, and it has not been entered
in Play Console. It describes the code in [`android/`](../android). The app shows
the same points in Setup → Privacy (`app/src/main/res/raw/privacy.txt`).

## Summary

Frame Control talks only to the user's own Steam Frame, at the address they choose.
It has no accounts, analytics, ads, crash reporting or servers of its own, and no
third-party SDKs that send data.

## Network

| Connection | Destination | What |
|---|---|---|
| SSH (TCP, default port 22) | The headset address the user chose: LAN, `frame.local`, or their own Tailscale name | Login, copying the server to the headset, commands, the tunnel |
| HTTP on 127.0.0.1 | This device only | The web view loads the page through the SSH tunnel |
| mDNS (NsdManager) | Local network | Looks for `_steamos-devkit._tcp` while setup is open |
| Links the user taps | System browser | Store pages, docs; opened outside the app |

Everything the page does (status, installs, store and catalogue lookups, Steam
downloads) runs on the headset. The headset itself contacts the services involved.
The page's Steam fonts/artwork and F-Droid catalogue icons are intercepted by
Android and fetched on the headset over an SSH command. Only the explicit HTTPS
asset paths in `AssetPolicy` are accepted, redirects are checked again, responses
must be image/font content and are limited to 8 MiB. At most four requests run
at once. Other external resource requests are blocked; screenshot blob images
remain local to the renderer. The headset's network address and requested asset
paths are visible to Steam/F-Droid asset services. No Frame Control server receives
them. The phone does not contact those services directly.
For the WebView, Safe Browsing is off, because only the app's own page loads
there, and WebView usage metrics are opted out (`MetricsOptOut`).

## Stored on the device

| Data | Where | Backed up |
|---|---|---|
| Headset address, port, user name | App-private SharedPreferences | No (`allowBackup=false`, every domain excluded from cloud backup and device transfer) |
| Headset host key (public) | Same | No |
| This device's SSH key | Android Keystore, non-exportable (StrongBox when available) | No |
| Page storage for the current tunnel | WebView, cleared at each new connection | No |

The Developer Mode password is never stored. It is held as a character array
only while pairing, sent only after the user confirms the headset's fingerprint,
and wiped afterwards. Neither the app nor JSch logs secrets.

## Stored on the headset

- This device's public key, one line in `~/.ssh/authorized_keys`, with the comment
  `frame-control@android-<model>`. Removing the line revokes the device.
- The server files in `~/.cache/frame-control/<version>`. Nothing runs from them
  after the device disconnects.
- Anything the user chooses to send, install or save there.

## Permissions

- `INTERNET`: SSH to the headset, and the local tunnel.
- `ACCESS_NETWORK_STATE`: to notice network changes and check the connection.
- `FOREGROUND_SERVICE` and `FOREGROUND_SERVICE_CONNECTED_DEVICE`: preserve the
  headset connection while a system document picker is in front.
- `CHANGE_NETWORK_STATE`: Android's normal permission prerequisite for that
  network-connected-device service. The app does not use it to change network
  settings.

The app requests no storage, media, location, contacts, camera, microphone or
notification permissions. Saving uses MediaStore (Pictures/Frame Control); sending
files uses the system picker, so access covers only the files the user picks.
A local connected-device foreground service runs only while a document picker
is open (up to three minutes), posts a temporary notification, and stops when the
picker returns or the Activity is destroyed. On Android 13 and later, without
notification permission the service appears in the system's Active apps list
rather than the notification shade. The app does not ask for that permission.
The service does not collect data or restart itself.
General downloads use Android's Create Document picker for a destination; tunnel
requests carry the per-session authentication header and reject redirects away
from the exact current tunnel origin. Image saves transfer one image at a time
in 192-KiB acknowledged chunks. Interrupted saves request deletion of incomplete documents through the selected
provider (some providers may refuse deletion); pending MediaStore images are discarded;
already completed images remain. Uninstalling does not remove exported images or
documents the user saved outside the app.
The clipboard is read only when the user taps the page's send-clipboard button. AndroidX adds
its own signature-protected `DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION`.

## Play Data safety (draft answers)

- Data collected: none. Data stays on the device, or goes to the user's own
  headset at their request. No data goes to the developer. The headset contacts
  Steam/F-Droid services for requested catalogue data and passive assets; assess
  those service-provider requests against Play's final definitions before filing.
- Data shared: none.
- Encryption in transit: yes. SSH covers all traffic to the headset; the
  127.0.0.1 hop never leaves the device.
- Deletion: uninstalling removes all app data. Forget removes the pairing, and the
  headset-side key line is removed by the user.

Check these answers against the final build before entering them in Play Console.
