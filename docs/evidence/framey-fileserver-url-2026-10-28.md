# DeckyFileServer 1.2.0 address correction, 28 October 2026

Official store ID 60 and ZIP SHA-256
`7dc2ecdcd05aa415d1ac90afaff28ecb17f77809a2bc7a77aee8e92505b976f0`.
The exact bundled frontend `dist/index.js` has SHA-256
`791015d8b3f234fad89ce422b09fb32bbad05e7c867d501706cfbcf9f7c6187f`.
Only that pinned managed archive receives this change. A changed archive keeps
the normal native/root rejection.

The [pinned corresponding Go source](../../ui/vendor/deckyfileserver-1.2.0/README.md)
calls `ListenAndServeTLS` for every server start. The official frontend instead
constructs `http://steamdeck:<port>` when uploads are off, and toggles the
second address between HTTP and HTTPS using the upload setting. Neither rule
matches the server. The `steamdeck` hostname also has no verified resolution
on Frame. Earlier [real Frame backend evidence](framey-fileserver-arm64-2026-10-27.md)
confirmed private HTTPS listing and download with uploads disabled.

The managed installer now checks the original frontend hash and replaces the
two displayed addresses with one `https://<backend IP>:<port>` address. A
rendered-element check executes the installed official bundle and verifies
that URL with uploads off and on; it also checks that no `steamdeck` address
remains. Receipts add `deckyfileserver-https-address`. Older managed copies
without it display an update or reinstall notice; the compatibility status
stays **partial**.

This check does not prove a live browser can reach every returned IP, or that
the folder picker works in Framey. Use a preconfigured directory. Uploads,
generated thumbnails, worn VR, physical controllers and wearer readability
remain unverified. This correction did not touch the real headset.
