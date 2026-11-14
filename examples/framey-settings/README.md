# Framey settings sample

This is a small Decky API v2 plugin for authors. Its panel uses the official
`@decky/api`, `@decky/ui`, and `@decky/rollup` packages. A toggle calls a Python
backend method, stores one boolean under `decky.DECKY_PLUGIN_SETTINGS_DIR`,
and reads it back when the panel opens. The backend rejects other keys and
values. The frontend also shows a local toast with a React body after a
successful save. The toast stays inside the Framey panel; it is not a Steam
system notification. A
Framey settings tab exposes the same toggle, and a read-only quick action
fetches the saved value without changing it. These two fields are Framey
additions; Decky's own menu still uses the main panel content. The quick
action calls the backend, so it reads the persisted setting rather than a
browser cache. A missing file or a valid object without `enabled` reads as the
caller's default without writing anything. Damaged JSON, invalid UTF-8,
non-object JSON and a saved non-boolean `enabled` value return an error on both
read and save. The original bytes stay untouched; the sample never treats an
unreadable saved value as a successful default read. Storage permission errors
also propagate instead of enabling editing.
To recover, preserve a copy of the damaged file in the plugin's settings
directory, then repair it or restore a known-good `settings.json` there.
Choose **Reload saved setting** to read the repaired value before editing.
The next successful save atomically replaces the sample's settings file.
Before replacement, the backend flushes Python's output buffer and calls
`fsync` on the temporary file. On platforms with directory descriptors,
including Decky's Linux backend, it also calls `fsync` on the settings directory
after replacement before returning a successful save acknowledgement. A file
flush failure preserves the previous file (or leaves a first save absent).
A directory flush failure happens after replacement: the new value can already
be readable even though the save returns an error. Use **Reload saved setting**
to reconcile it, just as for a lost reply; a rejected save does not mean a
rollback. All temporary files and opened directory descriptors are cleaned up.
Local tests inject both flush failures and read a successful save after its
backend process exits. They do not establish live-headset persistence or
survival of a physical power loss.
The current file is `{"schema": 1, "enabled": true|false}`. An unversioned
`{"enabled": true|false}` file from the first sample release still reads, and
the next save writes schema 1. A file with another explicit schema returns a
visible read or save error and remains untouched, so downgrading the sample
cannot erase settings written by a newer version. Add a deliberate migration
for each future schema instead of changing this guard silently.
The panel also guards its own read and write calls synchronously. If two
controller events arrive before React redraws a disabled control, the second
event is ignored; after a successful request settles, a new change can be saved.
If the initial read or a later reload fails, the toggle and Reset stay disabled
until **Reload saved setting** successfully reads the backend value. The last
displayed value is not permission to save after a failed read. This prevents
an unread setting from being overwritten using the initial display default;
callbacks retained before a redraw follow the same guard. Reload remains
available for recovery. This path is tested with synthetic backend replies,
not a live headset connection.

The frontend also validates runtime replies; `callable` type parameters do not
check values received from the backend. Only a boolean setting read enables
editing. A string such as `"false"`, a missing value or another JSON type shows
a read error and keeps editing disabled. Only the backend's literal `true`
save acknowledgement confirms success. A resolved `false` or malformed save
reply requires the same reload as a rejected request and never emits a success
toast. These cases are tested with synthetic replies through the built sample.

A rejected save reply can mean the backend committed the value but its reply
was lost. After any save error, the sample disables both mutations until
**Reload saved setting** succeeds. The displayed value is now unconfirmed;
it is not rolled forward or announced as saved. A failed reload keeps editing
disabled. A successful reload shows the backend value and enables editing
again. Tests use synthetic lost-reply and recovery cases through the built
bundle and real host; they do not prove live-headset persistence.

Leaving the settings view retires its callbacks, closes its Reset dialog and
ignores late read/write replies for that view's state and success toasts. A
request already sent to the backend is **not cancelled** and can still write
the setting. Returning to the view starts a new read before editing is enabled.
The sample also handles React's development effect setup/cleanup replay: a
late reply from the first setup cannot unlock or replace the newer read.
Lifecycle tests use delayed synthetic replies through the real host and built
bundle; they do not prove live-headset persistence.
An unfinished save also keeps a guard at module scope, so a newly mounted view
and the read-only quick action wait for its reply before reading the backend.
They read again after either success or failure; the requested value is not a
replacement for that read. A view closed while waiting sends no read, and two
settings surfaces cannot send competing saves from this loaded frontend.
The guard does not cancel a backend request or coordinate independent clients.
If a read was already in flight when another sample view starts a save, its
reply is discarded and a fresh read follows that save's settlement. This also
applies when the save finishes before the old read replies, whether the save
succeeds or rejects, and to the read-only quick action. Editing stays disabled
until a read completes without an overlapping save. A retired view sends no
replacement read. These cases use delayed synthetic replies through the built
sample; live headset persistence remains unverified.

**Reset example setting** opens a local `ConfirmModal`. **Keep setting** closes
it without a backend call; **Reset** saves `false` through the same guarded
write path as the toggle. This is a safe example of putting a settings change
behind an explicit confirmation in Framey. It has not been tried with a
physical controller in a worn headset.

The Reset callback returns the save promise to `ConfirmModal`. The dialog
stays busy until that save finishes, rejects repeat Reset/Cancel/Close actions
while pending, and stays open with an error if the save fails. Close it with
**Keep setting** or its Close button, then use **Reload saved setting** before
opening a new Reset dialog. Retrying the failed dialog before reloading sends
no write and cannot close it as a success. Only a successful save closes the
dialog automatically and shows a success toast.
Framey retires a confirmation's button handlers after it closes, unmounts
or completes successfully, so a retained Reset handler cannot issue another
save. A save already sent may still finish after programmatic dismissal;
reopen the settings view or reload to read its result.
The ordinary toggle catches the same rejected promise after `change` records
the error in the panel's status, so it does not create an unhandled rejection.
Do not discard an asynchronous confirmation with `void`: that makes the modal
close before it knows the result.

The **About this setting** button opens a local detail page at
`/framey-sample/details/saved-setting`. It demonstrates `routerHook.addRoute`,
`Navigation.Navigate`, `useParams`, `NavigateBack`, and removal of the route in
`onDismount`. The `:topic?` segment is optional. Framey keeps this navigation
inside the plugin panel; it does not open a Steam library page. Put optional
segments at the end of the path and do not use query strings. This detail page
has not been checked with headset controllers.

## Build

From this directory, run:

```sh
pnpm install --frozen-lockfile
pnpm build
pnpm exec tsc --noEmit
```

The committed `dist/index.js` is the built frontend. For a Decky release ZIP,
put `plugin.json`, `main.py`, and `dist/index.js` inside one top-level plugin
folder. Publish it through the official Decky store if you want Frame Control's
managed installer to offer it. Framey deliberately opens only plugins that the
official store installed and marked as owned; copying this example into the
plugin directory does not enable its VR panel.

From the repository root, pack and validate this sample without contacting a
store or headset:

```sh
python3 scripts/framey-pack-sample.py /tmp/framey-settings-sample.zip
```

The command packages the existing built frontend; run `pnpm build` first after
editing its source. It includes only `plugin.json`, `main.py`, and `dist/index.js`
under `framey-settings/`. Fixed file order, timestamps, permissions and uncompressed
ZIP entries make unchanged input bytes produce the same ZIP and SHA-256,
regardless of source modification times. The destination directory must exist.
The command checks a temporary ZIP with the author archive checker before
replacing the destination. A failed check leaves an existing ZIP untouched and
removes the temporary file. Its JSON result includes the output path and SHA-256.
For a renamed fork with this same three-file layout, use `--source path/to/sample
--name 'Exact Decky store name'`. Plugins with extra assets or chunks need their
own packaging step and `scripts/framey-check-archive.py`.

Expect `installerAccepted` and `panelCandidate` to be `true`. This only checks
local archive admission. Published store identity, Decky backend discovery,
frontend behavior and physical VR input need their separate tests.

## Test and adapt

Run `python3 -m unittest discover -s tests -p test_framey_sample.py` from the
repository root. It checks backend persistence and evaluates the built bundle
against Framey's actual host script, including the quick action's scoped
backend call, modal cancel/confirm behavior, and local route
registration/navigation. The fake Frame store flow is exercised by
the repository's e2e suite. No worn-headset visibility or controller-input test
has passed for this sample yet.

The separate native gate runs the shipped archive in the digest-pinned published
Decky 3.3.0 loader, without patching its backend. On native Linux with Docker:

```sh
python3 scripts/framey-test-sample-runtime.py --output /tmp/framey-sample-runtime.json
```

It saves and reads the real Decky-provided settings directory, stops and
restarts the loader, verifies readback, and checks that invalid writes and
malformed/future-schema settings are refused without replacing their bytes.
All three parent-only stops require zero exit, no forced plugin kill or shutdown
error, and no remaining recorded descendants. An unrelated private process
must survive all stops. AMD64 and ARM64 CI run this gate separately from the
mocked UI tests. Containers are nonroot, read-only and networkless, with private
writable homes and no host session bus or hardware. This verifies native backend
persistence; browser controls, real Frame persistence, worn visibility and the
VR keyboard still need separate checks.

The plugin needs no root access or system changes. Its settings remain after
the managed plugin folder is removed, following Decky's settings behavior.
For a production plugin, add explicit migrations for every supported schema,
explain how users can reset settings, and test every UI path in a worn headset.

## Browser settings through real Decky

On Linux with Docker and Chrome/Chromium available, run:

```sh
python3 scripts/framey-test-sample-browser.py \
  --browser /path/to/chrome --output /tmp/framey-sample-browser
```

The replay loads this unchanged built frontend in the actual opaque Framey
host. Its private test parent sends the rendered toggle and Reset confirmation's
requests to published Decky 3.3.0 in a networkless container over stdin. It checks
saved bytes and 0600 permissions, replaces the iframe to reopen the frontend,
and repeats readback after two complete loader restarts. Seven screenshots,
the real RPC transcript and recorded parent-only stops remain in the output.
The Linux AMD64 CI job requires this replay; native backend-only restart tests
continue to run on AMD64 and ARM64.

The parent, ownership receipt and DOM input are synthetic. This does not test
Frame's production HTTP/SSH parent, ARM64 browser behavior, a live headset,
physical controllers, scrolling, the VR keyboard or visibility in worn VR.
