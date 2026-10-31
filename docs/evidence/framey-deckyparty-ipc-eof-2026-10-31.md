# DeckyParty child IPC EOF, 31 October 2026

DeckyParty File Manager 1.0.0 (store 117) intermittently misses its unload hook
in published Decky 3.3.0. [Hosted AMD64 CI](https://github.com/saphid/frame-control/actions/runs/41189381617/job/124502812415)
force-killed the plugin on reload. A fresh local run against unchanged main
`d3ae60ebed19829e3a3ae43ed1ea3766e0cee45f` reproduced the failure; its full console
and exact-main source fingerprints are retained in the compressed evidence.
Earlier passing file-operation/reload fixtures did not establish reliable unload.

The exact managed archive now installs the existing child-local IPC EOF adapter.
Decky's original listener can repeatedly dispatch empty EOF without yielding,
starving unload. The adapter ends that connection's listener, preserving the
socket's ability to accept another connection. Existing framing/dispatch/error
behavior stays with Decky's implementation. The parent loader and other plugins
are unchanged. This does not change authentication or the original Copyparty
helper, frontend, manifest or license. Existing managed copies need Update/reinstall;
receipts missing `deckyparty-ipc-eof` receive that notice. Compatibility stays partial.

## Verification

The [independent audit](framey-deckyparty-ipc-eof-2026-10-31.json) binds all 16
native-source fingerprints to source commit
`8b46648df5e44e569dc2db098d8d57d038f0f65f`, the exact archive/loader digests,
and all original archive members except the adapted backend. A separate private
installation reconstructs the previous backend by removing only the adapter's
three import/install lines. Its digest matches the retained previous-source pin.
The [compressed raw evidence](framey-deckyparty-ipc-eof-2026-10-31-raw.json.gz)
contains complete native reports, phase/full consoles and unit output.

- 85 focused host tests pass, including exact archive scoping, installed receipt
  notices, the lifecycle contracts and IPC framing/EOF/exception contracts.
- Native AMD64 published Decky 3.3.0 discovers the installed plugin and exercises
  the original Copyparty helper on an owned anonymous disk volume. Authenticated
  private listing/download/upload/delete, anonymous/wrong-password refusals,
  disable/restart, independent disk bytes and unrelated-child preservation pass.
- Fifteen repaired RPCs and eight previous-source RPCs match literal expectations.
  Each reload deliberately opens and closes one private Unix peer before asking
  the actual parent loader to reload. This makes the disconnect reproducible;
  the original natural race sometimes completed without a forced kill.
- Three repaired reloads complete in 0.363, 0.366 and 0.394 seconds without forced
  plugin kills. Each unload hook runs, the recorded plugin identity exits and its
  recorded server identities disappear. Ancestry follows the actual plugin
  through Decky's multiprocessing infrastructure.
- The previous source force-kills once after 5.274 seconds without completing its
  unload hook and leaves one recorded server alive. The fixture signals only that
  exact owned server session. This is a negative control, not a compatibility pass.
- The repaired replacement and the negative run's fresh replacement each receive
  a parent-only SIGTERM and exit zero, in 0.214 and 0.164 seconds. Their unload
  hooks complete, recorded plugin identities disappear, no matching server is
  left, and the unrelated child survives. These final stops do not turn the
  negative reload into a clean result.

The fixture has no external network, devices, user session or writable host bind
mount. Complete consoles retain expected offline IP-discovery errors; an
error-free console and global clean shutdown across other plugins are not claimed.
Generic cleanup observes already-exited loaders and does not supply the explicit
reload/stop proof. The harness removes its containers, anonymous volumes and image.

Fresh exact-head hosted checks/e2e, native AMD64/ARM64 and triggered package gates
remain required. No new browser replay, LAN/HTTPS, external-media, managed Frame,
real Steam CEF, wearer-visible UI or physical-controller proof was performed.
No headset or hourly schedule was accessed and no release was published.

## Refresh onto merged TabMaster main

After #500 qualified and merged, normally merged current main
`0082d79a3ff9a9338e49dd5c83bbe25aa9e784b4` at tested source
`45f57b14811997bdedac47fbead080c541a36215`. There were no conflicts and no
history rewrite. The exact DeckyParty repair/helper/regression is retained,
as are main's complete TabMaster probe, all other probe bodies, all 34 native
case records (only DeckyParty gains its additional shim), published archive
inventory and shared IPC/console sources. All 116 status/install policies and
the other 115 complete catalog records match this main.

The refreshed source passes all 85 focused tests and a new isolated AMD64
published-Decky replay. All 16 source fingerprints match this source. Fifteen
repaired and eight prior-source RPCs, private file operations, three explicit
closed-peer reloads, the prior-source forced-kill/server-survival negative,
owned survivor cleanup and both final parent-only zero-exit stops independently
pass. The backend/adapter pins are unchanged. Complete available consoles and
the full unit output are retained in the new [refresh audit](framey-deckyparty-main0082d79-refresh-2026-10-31.json)
and [raw report](framey-deckyparty-main0082d79-refresh-2026-10-31-raw.json.gz);
the original evidence above is preserved.

This targeted replay does not qualify the full 42-probe/34-archive/16-source
hosted matrix. Current main 0082d79 and the final PR head need their own hosted
CI/e2e/native/package qualification; previous-head artifacts remain historical.
Compatibility stays partial. No new browser, LAN, managed Frame, wearer/controller
or release proof is added, and no headset or hourly schedule was accessed.
