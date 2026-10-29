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

The [hosted Decky runtime run](https://github.com/saphid/frame-control/actions/runs/40816672435)
passed both native jobs on code head
`77428f6bd79f827111d15f3b2f26b29e5bf867f8`. Its
[ARM64 job](https://github.com/saphid/frame-control/actions/runs/40816672435/job/123259448241)
discovered the same exact archive in published Decky 3.3.0 and returned the
same private account/empty-list RPC results. The downloaded ARM64 report has
SHA-256 `e0af84447ba7df68de39e66f67553d5e0589bc1e239886e86f0645b4ef88ce7e`.

These checks confirm current managed transport and a narrow native backend
path on x86_64 and ARM64. A nonempty supported-game scan, actual save
discovery, automatic backup, restore, the managed backend on Frame and worn VR
remain unverified. No backup or restore method was called. Steamback stays
**partial**.
