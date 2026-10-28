# Free Loader 1.6.0: private Decky backend check

The official store archive for ID 63 was downloaded and matched SHA-256
`05208aee6f6ba824391d8ddc81b1168b2599a9711e7528cdaa789f6cc710b42a`.
The published Decky 3.3.0 amd64 loader matched SHA-256
`e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181`.

An unprivileged, disposable Debian container ran that loader and the exact
official plugin with no network, host devices, host session or writable host
mount. Decky discovered Free Loader as enabled. Its API 1 methods returned 14
default settings and an empty local deals map. A private `larger_text` setting
changed to `true` and read back; startup created only the container's private
settings file, and `read_deals` created an empty private deals cache. No feed,
notification, Steam store or external account method was called. The local
probe exited successfully; its container was removed. The committed native
Decky runtime case repeats these calls and also checks persistence after a
loader restart on the CI runner's native architecture. The local x86_64 run
passed all 14 runtime cases, including Free Loader and the existing negative
regressions. The runner removed its temporary containers and image.

This strengthens the **partial** label. It does not verify a live feed refresh,
notification delivery, real Frame ARM64 service, rendered deal cards, worn VR
or controller interaction. The earlier opaque Chromium check had denied backend
and network calls, so it could not establish that deal cards render with live
data. No headset was touched for this check.

## Hosted ARM64 follow-up

The [main native Decky run](https://github.com/saphid/frame-control/actions/runs/40776292569)
on `dad5f78a02dd477a689689865cd4ef4205b87e22` passed the exact Free Loader
case on native amd64 **and ARM64** runners. Both logs report `PASS 63` for
discovery, default settings, empty local deals, private setting write/read and
restart persistence. The runners used separate network and device isolated
containers; no feed was fetched and no real Frame service was started. The
remaining partial-compatibility limits above still apply.
