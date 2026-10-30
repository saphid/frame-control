# Actual Syncthing runtime preflight, 30 October 2026

Syncthing **remains broken and blocked by the managed installer**. This
follow-up tests the uninstalled candidate against real Syncthing, rather than
the [earlier synthetic HTTP fixture](framey-syncthing-http-2026-10-30.md).
No runtime or helper executable is bundled or published. No real Frame was
contacted and no release is included.

## Pinned inputs

The official plugin is still Syncthing 0.2.7, store ID 64, ZIP SHA-256
`27e47379c280c92253d5533435f57c33b332b215f866d2ac4493daf18ec0d1c4`.
Its candidate ownership/private HTTP transport passed all 15 exact-head checks
on `863d77bbaaa149eb0bc5a67bcd1487efa6fb22f7` before
[#464](https://github.com/saphid/frame-control/pull/464) merged as
`d1379501f9091964b6c3a0011978ca063e0a4f1c`. Both native artifacts from
[run 41005829610](https://github.com/saphid/frame-control/actions/runs/41005829610)
were independently matched to that head's source fingerprints, build/helper
hashes and all ownership/transport states. Those earlier HTTP upstreams were
synthetic; they do not prove the real-runtime test below on ARM64.

The new test input is upstream
[Syncthing v2.1.7](https://github.com/syncthing/syncthing/releases/tag/v2.1.7),
published 21 October 2026. Archive hashes match both GitHub release asset digest
metadata and the published SHA-256 listing. PGP signature verification is not
claimed. The wrapper pins archive, executable and native ELF architecture:

| Architecture | Archive SHA-256 | Executable SHA-256 |
| --- | --- | --- |
| AMD64 | `2edc416e7ed136b7c858ed5f3f02a3b8316589605e54c380228ceea7acbf0142` | `f5c12679f2bad1b5eff619ba7b04ead1a457e439a1e55dc640d4d8995d7f4dbd` |
| ARM64 | `48e456690cd2b97e7d26b02b5ac35f62a3b36172267b144cfeaf02c993ab955c` | `3381c439af70c31db557d02581d0665d279f9efac1d0ea6806835a5b80dc65c7` |

Only the named regular tar member is read; archives are not extracted onto the
host. Inputs execute only inside the native unprivileged disposable container.
These portable binaries are test inputs, not a managed package/install policy.

## What runs

Two real Syncthing processes receive separate private homes, databases,
certificates and API keys. They bind loopback addresses inside a networkless
container. Global/LAN discovery, relays, NAT, usage reporting, crash reporting,
automatic upgrades and browser launch are disabled only in those new private
test configurations. Peer TLS and API-key checks remain enabled. No host user
session, devices or writable host path is exposed.

The fixture independently checks a 3,239-byte transfer and a reverse private
transfer by reading the receiving files. It then discovers the exact candidate
in published Decky 3.3.0 and calls its real legacy HTTP RPC. The request crosses
the Python private socket and original Rust proxy to the real Syncthing REST
API. Status/version, options, devices, device/folder stats, folders, folder
status and connections return the expected JSON shapes. A completion query
reports 100%, and a wrong API key retains Syncthing's real HTTP 403 response.

One retained runtime process restarts with the same database/certificates and
both received files remain intact. Decky exits within its eight-second budget,
reaps its owned watchdog and removes the private socket directory. Both owned
Syncthing processes must also stop and be reaped without SIGKILL before the
fixture can report success. The wrapper removes its owned container, temporary
input directory and image on either success or failure.

The first repeatable fixture incorrectly applied an eight-second shutdown
budget to Syncthing and caught a timeout after runtime restart. Upstream
v2.1.7 allows ten seconds for supervised-service shutdown
([svcutil](https://github.com/syncthing/syncthing/blob/v2.1.7/lib/svcutil/svcutil.go))
and another ten seconds for database close
([App.wait](https://github.com/syncthing/syncthing/blob/v2.1.7/lib/syncthing/syncthing.go)).
The test now uses a bounded 25-second runtime budget and signals both owned
peers before waiting. Decky's budget and the candidate watchdog's bounded
TERM/KILL/reap behavior are unchanged. Forced cleanup still fails the test.
The final AMD64 run reaped both runtime processes successfully within a measured
10.093-second upper bound from their stop requests. Sixteen compatibility/doc
contracts, Python syntax and generated-document checks also pass.

The [native report](framey-syncthing-runtime-2026-10-30.json) records exact
source/executable hashes and independent results. The local real-runtime proof
is AMD64 only; the same new fixture is required in the native AMD64/ARM64 CI
matrix before merge.

## Remaining gates

The fixture launches its own retained processes directly. No actual systemd or
DBus service manager is present, and candidate service setup stays disabled.
This does not establish the plugin wizard, Flatpak package, managed unit paths,
service start/stop, external-service selection, migration, or managed
install/update/remove. Those remain admission gates; existing unit/data
ownership must be protected before any real service operation.

Actual plugin browser controls, the complete Framey frontend-to-backend flow,
ARM64 real-runtime execution, real Frame runtime, wearer-visible rendering and
physical controllers remain unverified. The compatibility rating stays broken
and archive validation still refuses the exact official ZIP.
