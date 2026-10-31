# Simple Timer shutdown repair refreshed with main 3c03e47

PR #521 now includes main `3c03e478a2fab181e6bdfe60ada6038663843ab3` through normal merge
`4c224815029279f277986d2bc57e525b980f9a0f`, with parents `6b75b3a7587129ab88d750589fdaf1859117b849` and that main commit.
No history was rewritten. This incorporates the merged Free Loader and Deck
Settings repairs alongside the timer repair. Earlier green hosted heads remain
historical; they do not qualify this refreshed source.

## Verification at the combined source

- Published Decky **3.3.0 native AMD64** completed **45 probe assertion sets**,
  **34 archive pins**, **19 source fingerprints** and all **45 available console
  hashes** independently checked against this source. Probe completion is not a
  global clean-shutdown result. **No forced-kill marker appeared in the 34
  positive cases in this run.** Previous targeted Battery Tracker IPC/flush
  failures remain owned by #519; its repair is not included here.
- Repaired Simple Timer: **31 RPCs / 30 events**, including cancellation,
  replacement, completion, active-deadline persistence and canceled/expired
  restarts. Four clean parent-only stops took **0.196/0.215/0.235/0.215 seconds**. The original
  unload hook ran, exact settings bytes were preserved, owned identities were
  reaped, adopted children exited zero and an unrelated sibling survived.
- Original-source timer negative: **10 RPCs / 14 events**, retaining the
  task-state failures. Previous-managed timer negative: **18 RPCs / 24 events**,
  reproducing one forced kill. Neither negative is a compatibility pass.
- Current-main Free Loader controls retain **11/7 RPCs**, unchanged private
  settings/deal snapshots, two clean repaired stops and a forced original-source
  stop. Current-main Deck Settings retains **6/3 RPCs**, two clean repaired stops,
  the original unload hook, and a forced prior-managed stop. Both Deck Settings
  controls reject the self-signed upload endpoint before any HTTP request.
- Full server suite: **1,949 tests**, **16 platform/optional
  skips**, **257.041 seconds**, no failures. Website: **18 tests**,
  no skips. One isolated HTTP/SSH installer method passes all **37 pinned
  archives**, no skips, including exact timer receipt, backend/helper and removal.
  Owned containers, volumes, network and image tags were removed and absence
  independently confirmed. Generated compatibility docs and diff checks pass.

## Integration and archive audit

Only Simple Timer's catalog row differs from main; the other **115 complete
rows**, all **116 install policies**, other **33 native cases**, other **36
runtime handler bodies**, non-timer installer branches and non-timer HTTP/SSH
assertions are preserved. The existing Free Loader and Deck Settings helper
sources match main. The shared IPC adapter and original timer helper files are
unchanged. A runner AST comparison removes only the two added timer fingerprints
and the timer negative to reconstruct current main exactly.

Independent production installation at main and this source proves that the
timer backend adds only the EOF prefix to the prior managed lifecycle repair.
Its helper matches the shared adapter; both receipt shims are required. All
eight other published archive members are byte-identical. Compatibility remains
**partial**, and old managed copies need Update/reinstall.

[Structured audit](framey-simple-timer-main3c03e47-refresh-2026-10-31.json) and
[compressed raw evidence](framey-simple-timer-main3c03e47-refresh-2026-10-31-raw.json.gz) retain complete native records,
available consoles/hashes, timer RPC/event expectations, settings and process
readbacks, source-integration assertions, unit/website and installer logs,
owned cleanup records and verification scripts. All 19 fingerprints bind to the
merge source above. A subsequent evidence-only commit must preserve them.

## Remaining gates and limits

This is local native **AMD64** evidence. Fresh final-head hosted CI/e2e,
native AMD64/**ARM64**, PC/ownership checks, all triggered package modes,
current main, mergeability and unresolved feedback remain merge gates. Other
probes do not uniformly enforce graceful shutdown; all selected diagnostic and
forced-kill observations remain explicit. No globally clean runtime is claimed.

The HTTP/SSH method verifies installer/receipt/removal transactions; it does not
execute official plugin backends or the full e2e suite. No new browser, managed
Frame, wearer-visible, controller, sound, suspend or release proof is claimed.
Sound and suspend remain unsupported; alerts require an open panel. No headset
or hourly schedule was accessed. A release remains held until every exact
release-commit gate and locked real Frame smoke passes.
