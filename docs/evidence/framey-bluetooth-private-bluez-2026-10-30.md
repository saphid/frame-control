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
**fresh exact-head CI remains required after the current main refresh**. The compatibility row
remains partial. No new browser, real Steam CEF, actual adapter permissions,
radio connections, pairing, Frame display or physical-controller claim is made.

Reproduce on native Linux AMD64 or ARM64:

```sh
python3 scripts/framey-test-decky-runtime.py --case 18 \
  --output /tmp/new-owned-bluetooth-report.json
```

Both native CI architectures passed at historical head 3132115db3262a7666185175c0accd88748b23d0: 34 probes and 31 official archive digests per architecture, including this case's 13 actual API1 RPCs. The [native CI audit](framey-bluetooth-private-bluez-native-ci-2026-10-30.json) binds both completed jobs, artifact digests and actual checkout trees. Its [e2e audit](framey-bluetooth-private-bluez-e2e-2026-10-30.json) confirms the same complete source tree passed the integration suite.

All four historical signed-package artifacts also passed independent source, signature, actual runtime, two-way sync, migration, lifecycle and preservation audits. These test the shared runtime and do not add Bluetooth hardware scope: [AMD64](framey-bluetooth-signed-package-ci-amd-2026-10-30.json), [ARM64](framey-bluetooth-signed-package-ci-arm-2026-10-30.json), [browser HTTP](framey-bluetooth-signed-package-ci-http-2026-10-30.json), and [production-parent HTTP](framey-bluetooth-signed-package-ci-parent-2026-10-30.json). All distinct browser captures were visually inspected. The guest's complete loader-log checks passed; raw loader logs are not retained in these package artifacts for independent inspection. Both observed mixed-policy Decky stops reach inactive/success with zero PID and exit status.

The branch is now normally merged with main d89291e. The conflict resolution keeps both this BlueZ case and the published Terminal import regression; release verification changes are retained. Historical green results above do not qualify this refreshed head for merge. Its fresh core/e2e/native/package gates and resulting main CI remain mandatory. No real Frame or radio was contacted.

The refreshed AMD64 private native replay also passes all 13 RPCs and clean shutdown. Its [working-tree fingerprint report](framey-bluetooth-refreshed-native-local-2026-10-30.json) binds all seven native runner inputs after resolving the merge. It supplies local confirmation; fresh exact-head CI remains required.

The completed source `6a2175e3f7fbfd1388db54a08a5942b0e7b5e4fd` passed all 16 checks and all four workflows, with independent audits of both native architectures, the exact e2e tree and all four signed-package variants. Its [completed source audit](framey-bluetooth-completed-source-ci-2026-10-30.json) preserves job/archive/source identities and strict runtime/shutdown results. The [private published-frontend replay](framey-bluetooth-browser-2026-10-30/README.md) now retains the complete checksummed packet, 90 product fingerprints, all 31 unchanged published files, four inspected captures and raw loader logs inside its result. This private AMD64 synthetic BlueZ/bridge/input replay covers disconnect/reconnect, power off/on, disabled rows while off, refresh and loader restart; it adds no real radio/pairing, production HTTP, Steam CEF, Frame or controller claim.

After all original source workflows finished, the evidence commit was normally merged with main `445df0a6d1247dde2f40c156c4586381be9cd91d` without conflicts. Both sets of independent compatibility evidence and the host shutdown verifier are retained. The source-scoped passes above do not qualify the refreshed head: fresh exact-head CI, both native architectures, e2e, packages and resulting main must pass before merge. Compatibility remains partial with all admission policies unchanged.
