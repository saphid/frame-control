# Syncthing service-file ownership preflight, 30 October 2026

Syncthing 0.2.7 (store ID 64, exact published archive SHA-256
`27e47379c280c92253d5533435f57c33b332b215f866d2ac4493daf18ec0d1c4`)
**remains broken and rejected by the managed installer**. This is an uninstalled
candidate. No executable is bundled, no release is attempted and no real Frame
is contacted.

## Problem and change

The original helper wrote `decky-syncthing.service` without ownership checks,
then disabled/deleted that path when switching to an external service. The
wizard also called stop before initialization. Checking only the write path
would therefore leave service operations able to target a foreign unit.

The candidate uses a separate `frame-control-syncthing.service` below the
actual user's canonical home, with a fixed version header and a sidecar holding
the exact unit bytes. Both must agree before updates, removal or managed
start/stop/state. Missing or torn ownership fails closed. Existing unowned or
edited files are preserved. Legacy `decky-syncthing.service` files are never
automatically adopted, disabled or deleted. Explicit external-service selection
retains upstream semantics, except the new managed name is reserved and cannot
bypass its guard by being selected as external.

Preflight rejects symlinks, hardlinks, wrong-owner and oversized regular files,
and non-owned/symlinked or group/other-writable `.config/systemd/user` parents.
A persistent lock serializes cooperating candidates and remains held across
managed DBus operations. Updates retain the current unit mode; sidecars use
0600. A two-file interruption preserves the mismatched files and requires
manual recovery rather than guessing which file to delete. This is not
protection from arbitrary concurrent same-UID writers. Temporary partial files
from a failed write can remain for diagnosis; none is adopted as an owned unit.

Flatpak unit arguments are bounded literal tokens. Whitespace, control bytes,
systemd `%` expansion, `$` expansion and option injection are refused.
External transition stops and disables only a proved owned new unit before
removing it; failures propagate. Authentication and TLS code are unchanged.

## Verification scope

Nine Rust tests exercise actual private filesystem creation/update/removal,
legacy-file preservation, foreign and edited units, symlink files and parents,
hardlinks, corrupt/missing/torn receipts, concurrent lock refusal literal
argument validation and private directory modes. The native builder runs these tests before compilation
and records their execution and the module fingerprint. The same tests run on
each native AMD64/ARM64 CI job. Cross-compilation alone is not native execution.

The published Decky 3.3.0 fixture additionally places private pre-existing unit
markers in its disposable home. Actual legacy RPC calls for reload, state,
start, stop and wizard start must reject the foreign unit before the absent
DBus manager or Flatpak executable can be reached. It also checks the reserved
managed name in external mode. Both markers and retained settings must survive.
The usual private HTTP, restart, reload, unrelated-process and cleanup probes
remain required. A separate real Syncthing v2.1.7 fixture checks two-way sync,
REST reads, API-key rejection, retained runtime restart and owned cleanup.

The corrected AMD64 candidate passed the actual Decky RPC checks above,
including preservation of both private unit markers and restoration of the
retained settings. Its helper SHA-256 is
`f38d6d6c75c7093b1d3f385e492e05d0e8a27f3cfcc76c9c5fc113fdcbf4ac1e`.
The same helper also passed the real Syncthing v2.1.7 two-way sync, restart,
Decky REST/HTTP 403 and cleanup fixture. Both peers were reaped with successful
exits within a measured 10.083-second upper bound. Service setup stayed disabled.
All nine filesystem tests, 15 Python ownership/transport tests, 16 compatibility
contracts and 30 panel transport tests passed. Initial integrated builds caught
a missing module in upstream's separate library crate and its home-error type
conversion; both were corrected before the successful helper/RPC run. Review
also tightened newly created directory modes and added the ninth regression.

The [machine-readable local report](framey-syncthing-service-files-2026-10-30.json)
records the completed local checks and exact input fingerprints. The helper
cross-compiled successfully for ARM64 as well; that binary was not executed locally.

The final ownership head `8892ccac2ffac7c125f6575c8b7ee8d3e16e40fc`
subsequently passed all 15 checks before #466 merged as
`4329334887f1608dab727a76a5d1b083768754d7`. Workflow `41009027176`
produced native AMD64 artifact `12956996815` and native ARM64 artifact
`12956572922`. Both were independently matched to committed source hashes,
helper/build/loader fingerprints, nine executed filesystem tests, ownership/RPC
results, real two-way sync, HTTP 403, completion 100 and owned cleanup. These
native container tests still did not provide a real service manager.

The preceding runtime-only head
`5fe2428d5351aa9fd49c88039d57108fb6c77671` passed all 15 checks, including real
Syncthing runtime tests on **both AMD64 and ARM64**, before #465 merged as
`3e42bf2cfd65750691690eba833e205c3fefd8cf`. Both native artifacts were independently
matched to committed sources, build/helper/loader hashes and all result states.
See the [runtime evidence](framey-syncthing-runtime-2026-10-30.md).

## Service-manager limit

An isolated unprivileged Debian user-manager probe was attempted with a private
home and bus, no network, a read-only root and dropped capabilities. Actual
`systemd --user` exited 1 without exposing a usable manager bus. A machine ID
was present and the cgroup filesystem was not writable. `systemd --user --test`
exited 0, but that parsing result is not service runtime proof. No precise
single root cause is claimed. Owned processes/container/image were cleaned;
no host security or cgroup settings were changed.

No real DBus/systemd service control was verified by this preflight. Loaded unit identity,
drop-ins, aliases, enable links, Flatpak package ownership, external-service
selection, migration from existing services and full managed install/update/
remove still need an appropriate owned service-manager fixture. A receipt on
disk alone does not establish which unit systemd would load. Browser controls,
real Frame runtime, wearer-visible panels and physical controllers also remain
unverified. Existing files and services must not be migrated speculatively.

The subsequent [service VM evidence](framey-syncthing-service-vm-2026-10-30.md)
records a separate actual systemd/DBus fixture and its narrower remaining limits.
