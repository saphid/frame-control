# SuggestMe 1.5.3 verified TLS fallback and native backend, 29 October 2026

The exact official store archive for ID 132 is SHA-256
`248294b5d6b9d5a5d635ce35f4b5185ce59d4e4fd59353e24df4b29d74c2ade4`.
Its `main.py` is SHA-256
`9c141daf754302698d3e3e9ced70e36e9a4beb0b04f794fb66e7e45bd3b8d6e3`.
The published `_create_ssl_context` tries certifi first, but its fallback sets
`check_hostname = False` and `verify_mode = ssl.CERT_NONE`. A managed install
of this exact archive now uses Python's verified default context on fallback.
Other archives and unmanaged copies are not changed. Existing managed copies
need Update or reinstall to receive the fix.

A local managed install/remove test checked the pinned ZIP and source digest,
receipt shim, and installed source. It executed the installed fallback with a
simulated certifi failure and confirmed `check_hostname=True` and
`verify_mode=CERT_REQUIRED`.
The full local Python suite passed 1,722 tests with 16 skips. Its first run in
the default tool sandbox could not open test-owned loopback sockets; the same
suite completed with loopback access. Focused store and runtime-coverage tests
also passed.

The published Decky 3.3.0 x86_64 loader (SHA-256
`e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181`)
discovered the exact plugin in a disposable, network- and device-isolated
container. Without credentials or library data, its public RPCs returned
default configuration, empty library status and an empty suggestion. A private
filter preset saved, read back and survived a loader restart. The local report
`/tmp/framey-suggestme-native-x86_64.json` has SHA-256
`183f37d54eeab6ae47bd24475ad8dac99412e9f236c4cfb736c60335df499a3a`.
This local run was **x86_64**.

No Steam API key, account, owned library, outbound request or real Frame was
used. Recommendation quality, authenticated Steam/RAWG requests, native ARM64
Decky behavior, managed Frame install, in-VR UI and physical controller use
remain unverified. The compatibility status remains **partial**.
