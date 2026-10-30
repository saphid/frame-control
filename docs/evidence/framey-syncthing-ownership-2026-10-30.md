# Syncthing ownership candidate, 30 October 2026

Syncthing **remains blocked**. This change prepares and tests ownership of its
watchdog; it does not admit the official archive, ship a replacement executable,
or establish working synchronization. The compatibility rating stays broken.

The exact official **Syncthing 0.2.7**, store ID **64**, ZIP SHA-256 is
`27e47379c280c92253d5533435f57c33b332b215f866d2ac4493daf18ec0d1c4`.
Upstream tag v0.2.7 points to
`464fd7ca05ee0bea8daa8d5d125dfc672cf08942`; its `main.py` matches the
published ZIP. The original helper is x86_64. The original reset function would
spawn `/usr/bin/pkill syncthing` on this Linux fixture: this was observed with
all subprocess creation mocked, without signalling anything.

The original Python discards a detached watchdog handle and has no unload
method. Its reset/migration can kill unrelated Syncthing processes by name.
The Rust helper treats an executable-name substring as PID identity and
initializes systemd before it discovers a listener conflict on port 58384.

## Candidate

The retained `Popen` handle owns one process session. Restart and unload send
TERM, wait up to two seconds, then KILL and wait one second if necessary. The
handle is retained if reaping fails. Unload refuses late restarts. Migration
stops only an owned child and never finds processes by name. PID cleanup checks
the child PID under the helper's exclusive file lock and preserves a successor.
The persistent lock inode is retained to prevent two different lock files.

The Rust patch acquires that lifetime lock and reserves the fixed listener
before changing the PID, loading settings, opening logs or initializing systemd.
It removes executable/PID-file process discovery. A foreign listener or another
lock owner causes a failure without attaching to or signalling either owner.

The pinned original source, license, visible patch, candidate Python, isolated
builder and separate native CI gate are included. The managed installer has no
new exception for this archive. HTTP routes, service control, gamescope
monitoring, authentication and TLS code are unchanged.

## Evidence

- Full local regression: **1,784 tests, 16 platform/tool skips, zero failures**
  in **212.107 seconds**. These skips are not hardware verification.
- Eight Linux ownership contracts pass, including real owned/unrelated process
  checks, bounded escalation, failed reap retention, repeated startup, late
  restart refusal, PID cleanup and migration scope. They also pass under
  Python 3.9 in a read-only, network-isolated container.
- Both x86_64 and AArch64 candidates compile offline with frozen dependencies
  in Rust 1.98.1 Bookworm. The builder validates ELF machine values and records
  source, patch, Python, lockfile, image and binary SHA-256 values.
- Published **Decky 3.3.0 x86_64** discovers the candidate with the original
  manifest. Real legacy RPCs read disabled defaults and restart the owned helper.
  A private foreign listener is preserved, with invalid settings and no log
  directory proving refusal occurs before settings/service setup. A duplicate
  lifetime lock is refused. A forged PID value does not affect an unrelated
  process with the matching watchdog name. Three active plugin reloads reap the
  prior native child. Decky exits without SIGKILL and the final helper stops.
- Native execution uses an unprivileged disposable container with no network,
  host session bus, devices or writable host bind mount. Build containers expose
  only an owned build directory. Owned containers and temporary images are
  removed. The JSON report records the probe source fingerprints.

See [source/build/native report](framey-syncthing-ownership-2026-10-30.json).
Exact-head CI, including the new native ARM64 candidate probe, remains a merge
gate. Native test jobs upload logs and JSON only, not executable release assets.

## Remaining admission gates

The official frontend fetches fixed `http://127.0.0.1:58384` routes. Framey's
opaque iframe needs a receipt-bound HTTP bridge to that specific local origin.
It must not become a general network proxy.

The actual controls use systemd over DBus. A fake `systemctl`, settings-only
RPC or healthy listener does not prove service startup or synchronization.
Verify a supported Syncthing runtime/package, private real service behavior,
managed unit paths and migration behavior before admission. Original automatic
session detection watches `/usr/bin/gamescope-session`, not SteamVR. The
original loopback TLS proxy behavior is unchanged by this candidate.

ARM64 runtime, browser controls, real Syncthing service control, synchronization,
managed install/update/remove, real Frame, wearer-visible rendering and physical
controllers remain unverified at the time this local evidence was recorded.
No real Frame was contacted and no release is included.
