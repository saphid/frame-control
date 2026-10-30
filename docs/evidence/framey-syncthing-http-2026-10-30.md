# Syncthing private HTTP candidate, 30 October 2026

Syncthing 0.2.7 (store ID 64) **remains broken and blocked by the managed
installer**. This follow-up adds an ownership-bound transport to the candidate
from [#463](https://github.com/saphid/frame-control/pull/463). No executable is
bundled or published. No real Frame was contacted and no release is included.

The exact published ZIP SHA-256 remains
`27e47379c280c92253d5533435f57c33b332b215f866d2ac4493daf18ec0d1c4`.
The pinned original source archive and Cargo.lock are unchanged. The
[source/build/native report](framey-syncthing-http-2026-10-30.json) records the
candidate fingerprints and precise verification scope.

## Transport

The original frontend fetches `http://127.0.0.1:58384` routes. Forwarding those
requests through that TCP listener would risk reaching another process after
an unsuccessful startup. Instead, the retained Python owner creates a private
0700 temporary directory and passes its socket path directly to its child.
The Rust helper reserves the existing TCP listener, then binds the private
0600 Unix socket before PID, settings, log or service setup. Both listeners
share the original handler; existing routes, service logic, authentication and
TLS behavior are retained.

The Python RPC uses only its retained child's private socket, with no TCP
fallback. It accepts fixed GET/POST routes and bounded selected headers,
rejects other origins and encoded paths, caps responses at 256 KiB, rejects
truncation and invalid UTF-8, preserves HTTP error status and does not follow
redirects. Socket operations normally have a five-second timeout. The setup-start
check needs twenty seconds because its original handler deliberately waits up
to eleven seconds; neither value is a total request deadline. Four request
slots stay occupied until their socket workers finish, including after RPC
cancellation. Restart, reload and unload clean the
owned temporary directory after reaping the child; failed reaping retains it.

The inactive host facade preserves the original frontend URLs and legacy RPC
shape. It supports the exact frontend's requests, rather than the full Fetch
API. Its use requires ID 64, the exact published digest and a dedicated
`syncthing-owned-native-http` receipt shim. No installer produces that shim.
Other panels retain their existing transport. The archive is still refused.

## Verification

- Full final local regression: **1,794 tests, 16 platform/tool skips, zero failures**, in **216.556 seconds**. Skips do not establish hardware verification.
- Fifteen Linux contracts cover ownership, private HTTP request/response
  behavior, no TCP fallback, route/header refusal, response bounds, truncation,
  redirects, slow setup checks and cancellation retaining worker slots. They
  also pass under Python 3.9 in a read-only, network-isolated container.
- The Rust helper builds offline with frozen dependencies for AMD64 and ARM64.
  Two independent builds match byte for byte on each architecture; no candidate
  executable is shipped. Source, patch, lockfile, image and helper digests are
  recorded in the JSON.
- The host facade runs in a Node VM using the actual host source. It verifies
  legacy envelope shape, fixed origin, selected headers, method/body/abort
  refusal and HTTP error/empty response behavior, with no native network calls.
  Panel tests cover the exact digest, receipt shim and legacy-method gates.
  This is **not Chromium or actual plugin browser rendering evidence**.
- The published Decky 3.3.0 AMD64 native probe discovers the candidate, verifies
  disabled defaults and ownership conflicts, and performs real legacy HTTP
  RPCs through the private socket and original Rust proxy to a synthetic
  upstream HTTP fixture. An encoded query and fixture API-key/error status are
  preserved. Owned restart, three reloads and loader shutdown reap the helper
  and remove its private directory while preserving an unrelated process.
- The native runner uses an unprivileged, networkless disposable container
  without host devices, writable host paths or a host session bus. Test
  containers and temporary images are removed. Build outputs are local test
  inputs, not release assets. Exact-head native ARM64 CI remains a merge gate.

The Rust build report captured the candidate Python fingerprint before the
Python-only setup-timeout correction. Rust source, patch and both helper hashes
are unchanged; the native report and contract tests identify the corrected
Python independently. Exact-head CI rebuilds and tests the complete candidate.

## Unverified admission gates

The upstream HTTP fixture is synthetic. It proves transport, not a real
Syncthing runtime, DBus/systemd service start/stop, synchronization or actual
authentication against Syncthing. A supported runtime/package, managed unit
paths, migration behavior, real browser controls and managed
install/update/remove still need verification before admission.

Gamescope process detection is not SteamVR detection. Real Frame runtime,
passthrough pixels, wearer-visible panels and physical controller interaction
remain unverified. The separate hourly headset schedule owns those checks.
