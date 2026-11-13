# DeckyFileServer ARM64 backend — 27 October 2026

DeckyFileServer **1.2.0**, official store ID **60**, moves **broken → partial**
only for the exact managed archive
`7dc2ecdcd05aa415d1ac90afaff28ecb17f77809a2bc7a77aee8e92505b976f0`.
[Redacted observations](framey-fileserver-arm64-2026-10-27.json).

## Confirmed blockers and adaptation

The published ZIP contains a 19,779,282-byte x86_64 Go helper and requests `_root`.
Its actual operations use ordinary file permissions and an unprivileged port.
The managed installer replaces only this digest's original helper, checks the
replacement hash and ELF machine on the Frame, and removes only this manifest's
root request. Unknown versions, other binaries and root plugins remain blocked;
the Frame repeats archive/root/binary checks before extraction.

Pinned upstream commit `dcf3f3ce5104d05811fa8c156c4f58632b84b313` has Python,
manifest and package metadata byte-identical to the store archive. The published
Go executable lacks a VCS revision, so that binary's source revision cannot be
independently established. The rebuilt static Linux amd64/ARM64 helpers use
Go 1.25.7 and vendored dependencies. Complete corresponding GPL source, dependency
licenses, build recipe and hash pins ship with both desktop and headset bundles:
[provenance](../../ui/vendor/deckyfileserver-1.2.0/README.md).
The sole Go change sends its log to Decky's per-plugin log directory instead of
one global `/tmp` file. No compiler, pip, root service or runtime download is used.

Actual published Decky 3.3.0 discovery/public API1 RPC reproduced a hostname-DNS
failure in `get_status`. A local-address fallback selects the kernel source IP
without sending a packet, or returns loopback when no route exists.
The original command array includes empty strings for omitted flags; Go stops
parsing there and silently ignores the following `-disablethumbnails` flag.
The shim filters empty arguments and applies the thumbnail setting before start.
A negative runtime case restores the original empty arguments and proves that
thumbnails remain enabled despite the setting. **Decky 3.3.0 does expose
`decky.HOME`**; an initial assumption that it was removed was disproved by the
actual runtime. That API call and the plugin's API1 instance convention stay intact.

## Verification

- **Published Decky 3.3.0 amd64:** actual discovery, default settings, public
  API1 calls, native HTTPS directory listing and marker download, disabled
  thumbnails, upload endpoint returning 401, history and server stop. Execution
  used an unprivileged, network-isolated, read-only disposable container.
- **Real Frame ARM64, Frame OS 0.5.6:** the same useful backend actions passed
  through Steam CEF's existing Decky websocket, using a bounded private user
  service and a directory containing only public test markers. No home directory
  was shared and uploads stayed off.
- **Local Chromium opaque iframe with the actual Frame backend:** official
  warning, Enable Server, stop, settings modal and panel reopen with persisted
  private directory passed. A separate LAN host downloaded exactly the public
  marker over HTTPS after the panel started the server. The relay allowed only
  safe settings on that private directory; it denied uploads and other methods.
- **Fake Frame:** pinned archive install/remove, original frontend bytes,
  replaced native helper hash, root-free manifest and managed shim receipt
  passed through HTTP and SSH. Fake Frame does not execute plugin backends.

The shared `/tmp/frame-test.lock` was acquired normally and released after each
run. Two private test-adapter errors and an early LAN-readiness assertion were
corrected before the successful run; all attempts cleaned their private services
and artifacts. Normal managed Decky remained failed and the panel inactive,
matching their original states. Battery stayed **100 → 100** and no power setting
was changed. An independent SSH audit confirms base/unit/upload absent,
`MainPID=0`, `LoadState=not-found` and lock absent. Chromium and the local relay
were closed. No worn-VR claim is made.

The final branch, including merged DeckySpy and Simple Timer, passes **1,662
Python tests (16 skipped)**, all **9** published Decky 3.3.0 amd64 probes, **46**
app tests and pinned fake-Frame install/remove. Both helper rebuilds match byte
for byte. The combined headset bundle is 12,485,251 bytes, below its existing
32 MiB limit, and includes both native dependencies plus GPL source/licenses.

## Remaining limitations

The official frontend advertises **HTTP** and a **steamdeck** hostname even
though its helper always serves HTTPS. Use `https://<Frame address>:<port>`;
the upstream public self-signed certificate produces a browser warning.
Its Steam folder picker is unavailable in Framey; tests preconfigured only the
private fixture directory. The thumbnail toggle also appeared unchecked in the
settings modal while backend state was true; saving that modal was not tested.
These are concrete frontend follow-ups, so the plugin remains **partial**.
Uploads, thumbnail generation, inactivity shutdown, protected-file permissions
and worn VR remain unverified. The server exposes its selected directory on all
interfaces without authentication; select only files intended for sharing on a
trusted network. Existing unadapted copies require managed update/reinstall.
