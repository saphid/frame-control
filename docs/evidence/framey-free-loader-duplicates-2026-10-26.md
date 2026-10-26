# Free Loader duplicate archive entries, 26 October 2026

The exact official Free Loader 1.6.0 archive is store ID 63, SHA-256
`05208aee6f6ba824391d8ddc81b1168b2599a9711e7528cdaa789f6cc710b42a`.
It has 23 ZIP entries. Seven names under `free-loader/py_modules/` occur
twice. Each duplicate pair has identical uncompressed bytes and file type;
five Python files and `.keep` differ only between mode `0644` and `0755`.
The directory entry is identical. No path escape, symlink or alternate content
was accepted.

The installer now accepts an exact duplicate name only when its bytes match
and its mode differs at most in execute bits. Both desktop validation and the
headset transaction enforce that rule before extraction. The existing member
count, unpacked-size, per-member-size, root, path and ARM64 checks still run.
Synthetic tests reject changed duplicate payloads and non-execute mode changes.

## Scoped verification

- The exact archive passed the revised validator. A private local transaction
  installed and removed its `free-loader` folder and receipt; cleanup left no
  plugin folder. The focused store suite passed 21/21 tests, including a
  duplicate-member install/remove and permission readback.
- After merging current main, the full local Python suite passed **1,637
  tests, 16 skipped**. The generated compatibility document check and
  whitespace check passed.
- The pinned official fake-Frame HTTP/SSH install/remove test passed with this
  archive alongside the other pinned fixtures. It ran in a uniquely named
  disposable Compose project; its containers, network and volumes were removed.
  The fake does not execute the plugin's Python backend.
- The current Framey opaque Chromium host on main `d963305` initialized the
  exact frontend. Its **Free Games** view rendered, then displayed “Failed to
  load games!” because the audit intentionally denied all backend/network
  calls. It attempted `settings_read`, `read_deals` and logger methods.
  The browser audit's former `local_bundle` stub had returned HTTP 404 after
  receipt-bound panel lookup was introduced; the audit now supplies the
  digest-checked bundle and receipt to the shipped panel renderer.
- Exact official Python backend code ran in a disposable Python 3.12 container
  with network disabled, read-only root, no capabilities, a private data mount
  and a minimal `decky` API stub. `_main`, `settings_read` and `read_deals`
  succeeded: 14 default settings, a 12-hour update frequency, an empty deals
  map, and only private `settings.json`/`deal_db.json` files. The container
  and its private files were removed. No feed refresh or notification ran.

This makes **partial** the accurate digest-scoped status. The earlier full
116-plugin fake-Frame catalog audit blocked this archive before the validator
change; the focused pinned flow now passes. Actual Decky 3.3.0 backend load,
live giveaway feeds, notification delivery, headset install, worn UI and
physical controller input remain unverified. No real Frame session or service
was touched for this change.
