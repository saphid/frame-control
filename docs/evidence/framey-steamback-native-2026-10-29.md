# Steamback 1.0.0-1 managed install and native backend, 29 October 2026

The exact official store archive for ID 46 is 90,658 bytes with SHA-256
`ed5f2fbb47cdfc3aa9a4349a139ab20c29976117a3be0de7e8a588bb265ee7f3`.
It repeats several directory and file members. Every repeated file has identical
bytes, with at most an execute-bit difference; the existing guarded archive
validator now accepts it. A focused transaction installed and removed that
archive in a private temporary home, checking the digest-bound receipt and
owned plugin folder. The original 116-plugin fake-Frame baseline was captured
before this duplicate-file guard and recorded a rejection; its historical
`archiveValidation` and `fakeFrame` observations remain in the catalog.

`python3 scripts/framey-test-decky-runtime.py --case 46` then installed the
same pinned archive into a disposable, network- and device-isolated x86_64
container with the published Decky 3.3.0 loader. Decky discovered the legacy
plugin. Through its public RPC, a private account ID was added in memory,
`get_saveinfos` returned an empty list, and `find_supported` returned an empty
list for an empty input. The local report has SHA-256
`5e26ba48dfac902a9d0f2c87755002e7e62ba602113f6af97fd6523e3450046f`.
The runner removed its private container and image. No headset, real Steam
library or save directory was mounted.

These checks confirm current managed transport and a narrow native backend
path. A nonempty supported-game scan, actual save discovery, automatic backup,
restore, ARM64 backend, deployed Frame panel and worn VR remain unverified.
No backup or restore method was called. Steamback stays **partial**.
