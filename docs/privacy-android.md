# Frame Control for Android: privacy

Frame Control connects to the Steam Frame address you enter. It has no Frame
Control account, ads, analytics, or crash-reporting service.

The app stores the Frame address, user name, and accepted SSH host key in its
private storage. It creates an SSH key for this phone; the private key is saved
encrypted with a key held by Android Keystore. The Developer Mode password is
used for pairing and is not saved. Android backup is disabled for the app.

The app copies its server bundle to the Frame and loads the shared page through
an SSH tunnel. The page can request Steam catalog data, artwork, and trailers;
the Frame or the phone's WebView may contact the corresponding services. Links
you open can leave the app for a browser or another installed app. Files you
choose to send go to the Frame. Images you save go to the location you select
on the phone. Frame Control does not send this data to a developer-operated
server.

The app requests Internet access for the Frame connection. It requests
notification permission only when you use its local notification feature.
Uninstalling removes the app's local data. To revoke this phone's access to
the Frame, remove its public-key line from `~/.ssh/authorized_keys` on the
Frame.
