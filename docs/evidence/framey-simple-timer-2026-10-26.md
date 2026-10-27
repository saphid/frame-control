# Simple Timer lifecycle on Frame

The exact official Simple Timer 1.0.0 archive (store ID 96, SHA-256
`973d927e9d9a1feec04679c564af7e389a729b6735d2a988ffc2cb46ce4eb312`)
now qualifies as **works for silent in-panel session timers** after a managed
update/reinstall. The upstream BSD license and API1 manifest remain unchanged.
[Redacted observations](framey-simple-timer-2026-10-26.json) accompany this report.

## Reproduced failures and repair

The unmodified archive, discovered and called by the actual published Decky
3.3.0 loader, fails cancel before its first timer and expired-deadline startup
with an annotation-only `timer_task` attribute. Cancel leaves `timer_end` saved,
so canceled timers resume after restart. Starting a replacement leaves the first
task alive; it still sends its own completion event.

The managed installer repairs only this exact ID/digest/folder. Lifecycle state
is initialized before startup cancellation. A lock and cancellation/join give one
task ownership of the timer. Explicit cancel and completion clear the persisted
deadline. Backend unload stops the task while preserving an active deadline;
startup resumes that exact deadline without duplicating recent timers. Late
expiry emits its silent notice without canceling itself midway. Older installed
copies remain partial until their receipt includes `simple-timer-lifecycle`.

## Verification

- **Actual published Decky 3.3.0, isolated native amd64:** production managed
  install, API1 discovery and public instance RPC/events; fresh cancel,
  replacement suppression, one completion, clearing persisted end, active
  restart preserving deadline/recents, canceled restart and expired restart.
  A separate unmodified-archive case must reproduce the original failures.
  The same gate runs on native ARM64 CI; this report does not preclaim its result.
- **Real Frame ARM64, Frame OS 0.5.6:** the same lifecycle assertions through
  Steam CEF's existing `DeckyBackend`, with a bounded private Decky 3.3.0 user
  service and private settings. No plugin class was manually instantiated.
- **Local Chromium:** actual headset host and official frontend in a sandbox
  without `allow-same-origin`; method/event bridge relayed to that real ARM64
  backend. Begin created a 300-second timer; Cancel returned to idle. A safe
  five-second backend timer updated the panel and produced the visible silent
  completion toast. Backend tests verify persisted recents across restart;
  asynchronous UI recents after reopen were not asserted.
- **Fake Frame:** exact pinned archive installed and removed through the real
  HTTP/SSH store harness; execution is stubbed, so this verifies packaging only.

Only private settings and silent timers changed. The shared `/tmp/frame-test.lock`
was held for execution and then released. Successful run battery was 99 → 99;
normal Decky remained failed and the headset panel remained inactive as found.
An independent audit confirmed the private base/unit/archive absent, MainPID 0,
unit not found and no test client processes. Job-owned CEF event listeners and
private Chromium were removed. Two earlier test-client attempts were cleaned up:
one competed with Steam's single Decky websocket; the other lacked a bounded
quiet-event wait. Battery across those attempts was 100 → 99. These were test
adapter failures; the final run used CEF and passed.

Sound and suspend are unsupported. Alerts require the plugin panel to remain
open. Worn VR, physical controller/keyboard and sleep/wake notification delivery
remain unverified. A resumed timer is persisted backend behavior, not a promise
of notification delivery while the panel is closed.
