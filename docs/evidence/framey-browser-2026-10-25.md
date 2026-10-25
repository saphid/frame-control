# Framey loader evidence, 25 October 2026

## Local browser and fake Frame

The official Decky store returned 116 validated entries. ProtonDB Badges was
entry 14, release 1.3.4, SHA-256
`90a3453ac02709cad64096e7539fd8141fa56f99ae3441fc24a4990dc9684358`.
Its published ZIP passed Frame Control's store manifest and path validator. The current
`dist/index.js` bundle was loaded in an opaque-origin iframe in local Chromium
with the Framey React/DFL shim. The [browser screenshot](framey-browser-2026-10-25.png)
shows the plugin's settings panel. A pointer click on **Enable Badge on
Library** issued `set_setting('settings', …)` through the iframe's request
bridge. The local test parent returned a stub backend reply; it did not use a
real headset or Decky backend. A separate fake Frame CEF fixture returned
`get_setting` and `set_setting` responses through Frame Control's CDP bridge;
that fixture does not model the real Decky process.

The disposable fake Frame end-to-end harness passed the store catalogue,
acknowledgement and HTTP auth checks, hash-verified install, update, and
removal through the real Frame Control HTTP server and SSH transaction. The
full fake Frame suite passed 48 tests; the full unit suite passed 1,559 tests
(16 skipped). Unit tests covered unsafe archives,
unmanaged-folder preservation, asset isolation, backend-call scope,
and safe aborts of the worn-headset check.

## Real headset status

Read-only SSH on Frame OS 0.5.6 found battery at 98–99%. SteamVR activity was
initially 3 (standby), briefly 0, then 3 again. During the active probe the
shared `/tmp/frame-test.lock` belonged to `obs-aacapv3evh-20261025`. It later
became free after SteamVR returned to standby. Framey did not acquire, replace,
or remove it. The active probe found no installed Frame Control VR panel or
Framey plugin; the scripted worn check exited before acquiring a lock or
altering the headset. There is **no** wearer-visible VR
menu screenshot, controller-input proof, or live settings-persistence result
from this round.
