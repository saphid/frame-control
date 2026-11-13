# DeckyFileServer directory entry, 29 October 2026

The exact official DeckyFileServer 1.2.0 archive (store ID 60, SHA-256
`7dc2ecdcd05aa415d1ac90afaff28ecb17f77809a2bc7a77aee8e92505b976f0`)
uses Decky's native `openFilePicker(1, directory, false)` to choose the
directory its backend will serve over HTTPS. Chromium cannot return a native
absolute path from a browser directory picker. Framey therefore changes only
this digest-scoped managed bundle to show an explicit directory text field;
saved-history selection remains available. It does not expose a generic file
picker or filesystem enumeration API to plugins.

The fake Frame managed install checks the exact source hash and records the
directory-entry shim. A local Node rendering test opens the official settings
component, enters an absolute path with a space, rerenders it, and verifies the
path reaches the existing submit callback without calling `openFilePicker`.
The adapted backend refuses an empty, relative or nonexistent directory before
starting the server, so bad text cannot silently share its working directory.
The published Decky 3.3.0 amd64 runtime case verifies rejected empty, relative
and nonexistent paths, then private HTTPS listing/download from a fixture,
thumbnail policy and stop. This does not prove that an arbitrary chosen path
is safe to share. Users should choose only a directory they intend to expose
on their network and keep uploads disabled unless needed.

Earlier evidence verifies the native helper and a private real Frame HTTPS
listing/download. This change did not start the server on Frame or exercise
live path entry, uploads, generated thumbnails, worn VR or physical controllers.
DeckyFileServer remains **partial**. Existing managed copies need Update or
reinstall to receive this panel change.
