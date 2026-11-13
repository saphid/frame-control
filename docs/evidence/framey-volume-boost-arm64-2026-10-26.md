# Volume Boost sink controls on the ARM64 Frame

Volume Boost 0.0.7 (official store ID 58) now qualifies as **works for sink
controls**. The exact official, unmodified Python backend ran in Decky 3.3.0
ARM64 on Frame OS 0.5.6. Local Chromium rendered its official frontend through
Framey's existing legacy bridge. Actual control changes reached the Frame's
default speaker sink, including above-100% gain, with independent Pulse
readbacks. The sink stayed muted; no audible-output or worn-VR claim is made.

[Digest-pinned observations and cleanup](framey-volume-boost-arm64-2026-10-26.json)
record both runs. This supersedes the Volume Boost read-only limitation in the
[previous ARM64 audio check](framey-audio-arm64-2026-10-26.md). No plugin patch,
native rebuild or new compatibility shim was necessary. Volume Boost's backend
uses Python and the Frame's existing ARM64 `pactl`; its hard-coded UID 1000
matches the actual Frame user.

| Local Chromium action | Actual ARM64 result, independently read back |
| --- | --- |
| Linked numeric input 125% | Native Pulse channel values 81920 / 81920; plugin reads 125 / 125 |
| Linked slider click, then ArrowDown | 75% then 74%; native values 49152 / 49152 then 48496 / 48496 |
| Unlink, set left to 33% | Native values 21626 / 0; plugin reads 33 / 0 |
| Set right to 67% | Native values 0 / 43909; plugin reads 0 / 67 |
| Re-link | Official frontend issues a right-only 33% write; native values 0 / 21626 |
| Close and reopen | New document/session, ready; backend reads and displayed linked value return to the restored 0%; no mount write |
| Repeat linked numeric 150% with inherited service locale | Native values 98304 / 98304; plugin reads 150 / 150; reopen again reads restored zero |

The test restores the original sink state after **each** write. Therefore the
separate-channel checks intentionally begin from 0% / 0%, rather than from the
previous UI value. A right-only re-link request is the published plugin's
behavior. These checks verify channel selection and preservation of the other
channel; they do not claim a continuous unmuted listening session. Pulse's
integer conversion truncates fractional native values; the evidence retains
those integers rather than replacing them with rounded percentages.

## Runtime and transport

Each run separately acquired the atomic `/tmp/frame-test.lock`; neither stole
an existing lock. A unique private Decky user service used its own plugin,
settings and runtime directories, was never enabled, and had an eight-minute
runtime limit. The upstream ARM64 loader matched GitHub's published SHA-256
and ELF machine 183. The plugin ZIP matched the official digest.

The local relay served actual `ui/headset.html`, vendored React and
`framey-host.js`, with exact official frontend bytes in an opaque
`allow-scripts` iframe. Outer status/install/check responses were fixtures.
Plugin calls used production `framey_panel.call_method`, including the current
store receipt, SSH through lxso2, live Steam CEF and `DeckyBackend.call` into the
actual plugin subprocess. Only the temporary install paths were redirected.
This does not verify the deployed headset HTTP endpoint or a VR compositor.

The first private service explicitly used `LC_ALL=C`. The second inherited the
user-service locale without a `LANG` or `LC_ALL` override, matching the
production service configuration, and repeated actual reads, a 150% write and
reopen. Zero alone was not accepted as success: upstream returns zero on
command failure. Every write returned true, both backend channel reads agreed,
and independent native Pulse readbacks confirmed nonzero changes.

## Bounded muted writes and restoration

The default sink was already muted at native channel values 0 / 0. Before each
plugin write, a private device-side helper captured the exact sink identity,
channel values and mute state; persisted recovery state; and started a bounded
60-second systemd watchdog. It then required a successful mute readback before
allowing the plugin call. The relay allowed only `get_volume_state` and
`set_volume_state`, known channels and values from 0 through 150.

After the call, independent `pactl --format=json list sinks` and both plugin
reads checked the result. In `finally`, the helper restored exact native
channel values while muted, checked them, restored the original mute state,
and verified the entire snapshot before removing recovery state and stopping
its watchdog. No default route, playback, existing stream or power setting was
changed. Automatic watchdog expiry was armed but not deliberately exercised;
explicit restoration passed after all seven writes.

Both private Decky services/bases were removed and their locks released.
Fresh-lock cleanup audits found their Decky and guard units unloaded/inactive
with PID 0, paths absent, and the exact original sink/mute restored. Battery
stayed 100 → 100; normal managed Decky and headset-panel services stayed
inactive. Decky startup reinjects its frontend and can restart Steam CEF.

## Catalog and verification limits

The canonical store catalog and generated table report **4 works / 48 partial /
53 broken / 11 N/A**. A fresh full official-store fetch at 06:10:58 UTC found
all 116 IDs, versions and digests unchanged. Historical fake-Frame checks cover
this exact archive's install/receipt/removal with backend execution stubbed;
that test was not repeated or relabelled as real-backend evidence.

Audible gain, sound quality, physical speaker output, Bluetooth sinks,
headset-controller input and worn VR remain unverified. The store row includes
these limits. This change records new real-backend evidence and updates its
compatibility classification; it changes no shipped audio implementation.

The full server suite completed 1,626 tests with no failures (16 skips); all
18 site tests passed. Generated-document consistency and `git diff --check`
also passed. No implementation change followed those tests.
