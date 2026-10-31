# Syncthing helper lifetime after forced plugin exit — 2026-10-31

The [AMD64 ownership job for #501](https://github.com/saphid/frame-control/actions/runs/41158034008/job/124409075172)
failed at exact head `fd3b66162fadb2e7a442fd0ee220de445a1f68c1`.
Decky reported that the plugin stayed alive for five seconds after its stop
request, sent SIGKILL, then the next helper could not acquire its ownership lock.
The reason the original plugin did not finish unload remains unproven.

Published Decky **v3.3.0** implements this five-second fallback in
[`plugin.py`](https://github.com/SteamDeckHomebrew/decky-loader/blob/v3.3.0/backend/decky_loader/plugin/plugin.py).
The candidate's helper starts a separate session and previously depended on
Python `_unload` to stop it. Killing the plugin can bypass that callback and
leave the helper alive with the lock.

## Reproduction and repair

The unchanged candidate rebuilt with the exact CI Rust image and pinned sources
produced SHA-256
`bef65e425ff895dd40e932fdae424376988e6abed17a9527e4eda383002a578d`,
identical to the failed job's helper. In a disposable, networkless native AMD64
container, the published loader completed three normal reloads. The probe then
paused only the owning plugin, causing the loader's actual five-second SIGKILL
fallback. Reload failed with the same ownership error. This deliberately forces
the failure path; it does not reproduce the original reason unload stalled.

The helper now sets Linux `PR_SET_PDEATHSIG` so it dies if its spawning plugin
thread exits. Python supplies its PID before fork/exec; the helper checks that
its parent still matches before touching ownership, PID, settings or logs. An
invalid or changed parent is refused. A 500 ms lock retry budget permits the
kernel to finish a killed predecessor without bypassing a foreign lock. No
PID-file or executable-name signaling is introduced, and dependencies stay locked.

The corrected AMD64 helper SHA-256 is
`318c0c58bce164d5e23528ae0da40f7d142005984ff64801b74a36b790e456b0`.
Both actual-runtime reports independently match those helper bytes and every
listed production source fingerprint.

## Verification

- Published Decky 3.3.0: disabled defaults, private HTTP/error handling, foreign
  listener/unit/PID preservation, duplicate ownership refusal, owned restart,
  three normal reloads, and a forced plugin kill followed by successful reload.
  The final report retains and asserts the loader's SIGKILL console message.
- Actual pinned Syncthing **v2.1.7** peers: two-way private file sync, restart
  preserving files, completion=100, Decky RPC REST reads and a real 403 for the
  wrong fixture API key. Both peers stopped normally; all owned processes reaped.
- Full host unit suite: **1,912 tests**, successful with **16 platform/optional
  skips**, in 257.262 seconds. The focused ownership suite passed all **19** tests.
  Python compilation, fuzz-free patch application and `git diff --check` passed.

The probe uses Docker init to reap orphaned children. It explicitly removes the
private temporary socket directory of the deliberately killed Python owner after
proving the old helper exited. The kernel guard does **not** promise filesystem
cleanup after SIGKILL. Disposable containers and their data were removed, along
with the owned prepared test-image tag. Public build inputs and proof files were
retained locally for reproducibility.

## Limits

Base: `08bd8473b18c3d246a9c96d5e7a17ff4acaa3733`. This local proof is native AMD64.
Native ARM64, final hosted head CI, systemd VM lifecycle and signed Flatpak
package qualification remain required; they were not rerun locally for this
helper. The peer test uses private raw Syncthing processes, not a managed Flatpak
install. Browser rendering, the real Frame, worn VR and controller use are
unverified. No headset was contacted or sent input.

Syncthing remains blocked and unselected by the managed installer. All 116
catalog ratings, installer policy and compatibility-table claims match main.
No release is published by this fix.

[Full build/runtime records and source hashes](framey-syncthing-owner-death-2026-10-31.json).
