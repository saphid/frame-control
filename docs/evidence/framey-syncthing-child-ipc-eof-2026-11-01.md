# Syncthing child IPC EOF and normal reload

The ARM64 ownership job on PR #503 (`3f69495ddf6defedd77631466bdb07c4a1a2692e`, [job 124790960036](https://github.com/saphid/frame-control/actions/runs/41287255693/job/124790960036)) failed during a normal reload: Decky killed the plugin after five seconds and its private socket directory remained. The failed artifact digest was verified; it contains build records and no successful native runtime packet. This failure is retained, not rerun away.

Published Decky 3.3.0 dispatches empty input repeatedly after child IPC peer EOF without yielding. Its parent closes the response peer immediately after sending SIGTERM, so this loop can starve the handler that runs `_unload`. Syncthing's uninstalled candidate now installs the existing child-only EOF adapter; the parent loader and shared adapter are unchanged. Container, real-peer, service VM and signed-package payloads deliver and fingerprint that dependency. Syncthing remains blocked/unselected.

## Verification

Tested implementation: `98af6e28147eac7b473f311697cd29b3f283a9b0`, based on main `ad070b731386dfbc2c8ed24b901b0b5edaeacbf2`. Only evidence was committed afterward.

- A real extra peer connects to the current plugin child's own Unix socket and closes before each normal reload. With the unchanged backend, this deterministically reproduces Decky's five-second SIGKILL and the socket-directory assertion failure. An initial fixture attempt incorrectly counted listening and accepted socket rows separately; it was corrected to use unique paths before this red run and is not counted as product evidence.
- With the adapter installed, **three normal reloads** exit their old child and helper and remove their socket directories without a SIGKILL fallback. Observed reload/readiness times: 0.332s, 0.311s, 0.311s. The existing explicit SIGSTOP/Decky SIGKILL control remains separate and still proves helper owner-death handling; only that intentionally killed owner's directory is cleaned by the fixture.
- **112 focused tests, zero skips**: ownership/HTTP boundaries, shared EOF framing, package input/refusal/cleanup, rootfs packing, guest-result transport and captured command timeouts.
- **Native AMD64, published Decky 3.3.0**: actual Syncthing v2.1.7 peers transfer in both directions, retain files across restart, expose actual REST responses through the private-socket Decky RPC, preserve wrong-key 403, and reap the fixture's retained processes. The ownership probe's upstream HTTP server is synthetic; it is not counted as real Syncthing evidence.
- Source/digest audit binds both native reports to nine current source files, verifies the unchanged adapter and verifies the backend changes only by installing that adapter. It also reconstructs the red regression from the green fixture minus adapter delivery. The ScreenSaver merge between red and green left the imported RPC helpers unchanged.

Raw reports, red log, test output and failed ARM artifact metadata are retained in the adjacent compressed evidence file. Explicit probe cleanup assertions are source-bound; these records are not complete process/filesystem snapshots and do not establish a globally clean host. The separate strict-runtime evidence work in #513 is still required for its scope.

## Limits

No current-head ARM64, systemd VM, signed-package modes, browser, Steam CEF, Frame, wearer or controller proof was run locally for this fix. Hosted checks must qualify the exact published head before merge. No real headset was contacted, no release was qualified, and no compatibility rating or installer selection was changed.

## Announcement

The uninstalled Syncthing candidate can complete normal Decky reloads after a child IPC connection closes. A deterministic native AMD64 regression reproduces the old forced kill and verifies three repaired reloads. Syncthing remains unavailable for normal installation; ARM64, package, browser and Frame qualification are still required.
