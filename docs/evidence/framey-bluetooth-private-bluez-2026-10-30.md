# Published Bluetooth backend through native Decky, 2026-10-30

Bluetooth 3.1.1 (store 18, published SHA-256
`f07f7b74f31da15b5e3a8234a3f00faa01365b56b8f496aca7bb79120be7b8a5`)
had no native Decky CI case despite its existing frontend and direct read-only
Frame evidence. Add the exact unchanged archive to the native matrix with a
private synthetic BlueZ service. No production shim or plugin byte is changed.

The [local AMD64 report](framey-bluetooth-private-bluez-2026-10-30.json)
records 13 actual Decky API1 RPCs. The replay tested source bytes committed as
`644ad549a60fdff8b622c23a8232212adba3a654`; all nine recorded input fingerprints
match that commit. It used the digest-pinned published Decky 3.3.0 loader,
not a direct Python import or mocked Decky RPC handler. All 31 published
Python/JavaScript files in the installed plugin matched the archive.

The synthetic bus exports two adapters and three devices. The backend selects
hci1 because it owns paired devices, even though hci0 sorts first. Its list
filters the unpaired canary; device details preserve the alias, typed BlueZ
battery percentage and optional metadata. A second paired device has no
Battery1 interface and returns no battery. Missing-device defaults and failed
connection attempts leave the synthetic service unchanged. Disconnect/connect
and power-off/on calls round trip through D-Bus, restore the selected synthetic
device/adapter state, and preserve the other adapter. These are fixture
transport assertions, not Bluetooth hardware or pairing tests.

The container has no network, host home or system/session bus mount, drops all
capabilities and retains no-new-privileges. Only a bus socket created in its
private runtime directory is exposed as DBUS_SYSTEM_BUS_ADDRESS. The service
refuses to start if a system bus socket exists. Neither the service nor the
probe invokes a radio or discovers actual devices. The loader stops with
exit status 0 in 0.214 seconds; its retained log contains the unload marker and
none of the shutdown-error, cancellation or pending-task markers. The owned
private bus and service are reaped before a successful report is emitted.

The three existing runtime-coverage regressions, compilation and diff checks
pass. This adds the actual-runtime fixture to both native CI architectures;
**exact-head CI and ARM64 results remain required**. The compatibility row
remains partial. No new browser, real Steam CEF, actual adapter permissions,
radio connections, pairing, Frame display or physical-controller claim is made.

Reproduce on native Linux AMD64 or ARM64:

```sh
python3 scripts/framey-test-decky-runtime.py --case 18 \
  --output /tmp/new-owned-bluetooth-report.json
```
