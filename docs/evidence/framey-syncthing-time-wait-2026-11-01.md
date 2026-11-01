# Syncthing watchdog and closed TCP client sockets

Tested source: `1a6b974ae19716e919db8c27be9ed6b1b4fa487f`, based on main `770d57fd228786ee410a72e477f948805a928b11`.
Syncthing remains blocked. No installed plugin or release was changed.

## Reproduction and change

The exact old candidate helper `318c0c58bce164d5e23528ae0da40f7d142005984ff64801b74a36b790e456b0` reproduces
`Address already in use` in a fresh network-isolated container with no other
watchdog. An ordinary client bound to 127.0.0.1:58384 is actively closed and
leaves a real kernel TIME_WAIT row. SO_REUSEADDR still cannot bind that port.
The helper exits before touching settings, the PID marker or logs.

The fixed candidate retries address-in-use errors for up to 70 seconds only
when read-only kernel tables show conflicting IPv4 loopback TIME_WAIT rows
and no IPv6 use of that port. A live listener/client, unknown or malformed
table, unreadable table, other error or expired budget still causes refusal.
It never attaches to or signals the port owner. Listener reservation still
precedes PID/settings/log/service work; the lifetime lock and parent-death
guard remain in place. Startup fixture waits now allow 80 seconds. Shared
readiness keeps its 20-second default; shutdown checks and budgets are retained.

This demonstrates a reproducible mechanism for the same error seen in #519's
[failed AMD64 package job](https://github.com/saphid/frame-control/actions/runs/41256615977/job/124701022133).
That historical artifact did not identify its conflicting socket. This new
reproduction does not prove the historical cause, erase the failure or qualify
that old head. Its result/console and digest metadata are retained in the raw packet.

## Verification

- 1964 server tests passed with 15 platform/optional skips; 18 website tests passed with zero skips.
- Five native Rust classifier tests passed. Live TCP states, IPv6 ambiguity,
  malformed/absent tables and other I/O errors cannot authorize waiting.
  Package proof now rejects helpers without recorded native classifier tests.
- The fixed AMD64 helper `ef5f0e459b5b779488189108e95015f03f83f472ee02d69ae00dd3df7cffbe6b` waited for a real
  TIME_WAIT socket to expire in 63.356 seconds. During the wait,
  PID/settings/log/private-socket state stayed untouched. It then reserved
  the listener and reached the deliberately invalid settings. That intentional
  SerdeJson failure is preserved; it is not counted as a working service.
- Subsequent published Decky 3.3.0 AMD64 checks passed: private HTTP/auth errors,
  foreign listener refusal, unrelated service/process preservation, duplicate
  ownership refusal, owned restart, three normal reloads and a deliberate
  forced-plugin-exit control. The latter still checks that only the owned
  helper exits. Final loader shutdown and private socket cleanup passed.
- A separate pinned native Syncthing v2.1.7 AMD64 run passed two-way file sync,
  restart persistence, nine Decky private HTTP read routes, completion 100%,
  API-key rejection 403 and normal peer exits within the existing 25-second
  budget. Reported private marker hashes match independently specified bytes.
  This directly launches peers; it does not exercise systemd or a Flatpak.
- Source hashes bind the build and native reports to the committed inputs.
  Independent inspection finds owned build/probe containers and images gone;
  shared simulator/image identities are unchanged.

The first native attempt failed a fixture assertion that looked for the deliberate
settings panic on stderr. Upstream writes `last_panic.txt`; the corrected fixture
checks that owned panic file. The failed attempt is retained in the raw packet.

## Limits

ARM64, full native matrix/e2e, signed-package modes and exact publication-head CI
remain required before merge. This pass did not run full local e2e or a package
VM. The ownership fixture's upstream HTTP service is synthetic. The separate
real Syncthing peer run above proves private sync assertions for that pinned
native binary. Neither fixture proves a systemd service manager, actual signed
Flatpak package or official UI.
The managed installer still blocks Syncthing. Worn Frame visuals, controllers,
real Steam CEF and release smoke are unverified. No real Frame or schedule was
touched. Full release gates remain held.
