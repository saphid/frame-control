# Large Send to Frame files: source and offline verification

[Issue #373](https://github.com/saphid/frame-control/issues/373) reports that
a 26.5 GB file selected from external USB media failed with “empty or
too-large upload” in Frame Control 0.4.8. Current main still imposed an
8 GiB `POST /api/upload` body cap for **Send to Frame**, even in the desktop
app. The desktop already knows the selected local file path, but previously
sent the whole file through HTTP into another temporary copy before SSH.

The desktop page now passes that path to `POST /api/transfer`, which is
enabled in the app-started server. It checks for an absolute, nonempty
regular file and copies it directly by the
existing rsync/scp route to `~/Downloads`. This avoids both the 8 GiB HTTP
cap and a duplicate temporary file on the computer. The endpoint preserves
the selected-headset work guard. Large copies have a finite timeout that
scales with source size. Plain browser uploads still have an 8 GiB cap and
now state it before sending bytes; the page says which route applies.

Offline checks use a mocked 27 GiB file size without allocating that space.
They verify the direct server copy path, a timeout longer than one hour, the
page's desktop-versus-browser choice, and early rejection of an oversized
browser upload. Loopback tests confirm the browser cannot call the direct
route, reject a mismatched selected headset with HTTP 409, and accept the
matching desktop request with HTTP 200. Unit tests reject missing, relative,
directory, hidden and empty source paths before any SSH. The full Python
suite on the final branch passed **1,690 tests, 16 skipped**. Hosted CI is a
separate merge gate.

An actual 26.5 GB transfer from USB media to a Frame, end-to-end throughput,
resume after interruption and free-space behavior remain unverified. No real
headset or user file was touched for this change.
