# Third-party software in Frame Control

Frame Control's own code is under the [MIT licence](LICENSE). The apps also
ship other people's software, unchanged, each under its own licence:

| What | Where | Licence | Details |
|---|---|---|---|
| KDE Connect 24.02.2 and five libraries, as Valve builds them for the Frame | Desktop apps and the iPhone app; copied to the Frame for the keyboard and trackpad | GPL and LGPL (per package) | [frame/kdeconnect/NOTICE.md](frame/kdeconnect/NOTICE.md), licence texts in [frame/kdeconnect/LICENSES](frame/kdeconnect/LICENSES), complete source in the [kdeconnect-frame-24.02.2-1 release](https://github.com/saphid/frame-control/releases/tag/kdeconnect-frame-24.02.2-1) |
| psutil 7.2.2, unchanged stable-ABI Linux amd64/ARM64 wheels | Desktop and headset app bundles; copied only into exact managed DeckySpy 0.6.7 installs | BSD-3-Clause | [pins and provenance](ui/vendor/psutil-7.2.2/README.md), [license](ui/vendor/psutil-7.2.2/LICENSE.txt) |
| Python 3.12 ([python-build-standalone](https://github.com/astral-sh/python-build-standalone)) | Desktop apps | PSF License and others | Included with it, in the app's `python` folder |
| adb (Android SDK Platform-Tools) | Desktop apps (not Linux arm64) | Apache-2.0 and others | `NOTICE.txt` in the app's `tools` folder |
| Mozilla's CA certificate list, as published by curl | Desktop apps | MPL-2.0 | https://curl.se/docs/caextract.html |
| Electron | Desktop apps | MIT (Chromium: BSD-3-Clause and others) | `LICENSE` and `LICENSES.chromium.html` in the app |
| GStreamer 1.x, a few of its plugins and the libraries they need, as [MSYS2](https://packages.msys2.org/) builds them | Windows app only, for the experimental [PC in the headset](docs/pc-in-headset.md) | LGPL-2.1-or-later and others (per package); the GPL x264 encoder is left out | `libraries.json` (exact package versions) and the `licenses` folder in the app's `desktop/bundle` folder |

Frame Control starts KDE Connect and talks to it over its network protocol;
it doesn't link to it or include its code. On Windows, Frame Control's own
`pc-host.dll` links to GStreamer dynamically; the libraries are unmodified.
