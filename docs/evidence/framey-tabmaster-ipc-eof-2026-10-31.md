# TabMaster child IPC and strict shutdown gate, 31 October 2026

TabMaster's prior native fixture could report success after Decky force-killed
the plugin. A zero loader exit and reaped children did not establish clean
shutdown. The [RadiYo refresh](https://github.com/saphid/frame-control/blob/3bfccea94b5cdd13de055901d7dee47edc8f2002/docs/evidence/framey-radiyo-main-refresh-2026-10-31.md) retained
that failure on its separate branch. This scoped repair preserves TabMaster's
JSON backup/restore fix and applies the existing child-local EOF adapter only
to store ID 61, version 2.15.1, archive SHA-256
`e08333859a32b0c177b8e9a7959c5eeeafe38f946578f7f1d161c721f0e05da5`.

The strict test first failed at source `dade4536` without the new adapter.
Closing an owned IPC peer before signaling only the loader reproduced a
5.223-second stop with one forced plugin kill and no completed original unload
hook, even though the loader exited zero. The failure log and exact source
fingerprints are retained. This proves peer EOF can cause the observed failure;
the exact socket history of the earlier intermittent failure was not retained.

At runtime source `1bbcb6196158d114a2071ce1f46df33536762182`, published,
digest-verified Decky 3.3.0 ran in network/device/session-isolated native AMD64
containers. Its three cases made 47, 48 and 47 RPCs:

- The repaired backend retained private user settings, false values, shared-tab
  filtering, private backup/restore, malformed/non-object backup refusals and
  disk/restart persistence. It handled a closed peer and completed two
  parent-only stops in 0.214 seconds each, with its original unload hook,
  zero forced kills and zero adopted-child exit statuses.
- The original published backend reproduced valid backup-restore refusal,
  while retaining the other private settings/restart controls. Both normal
  stops completed in about 0.214 seconds. This control deliberately receives
  no extra closed peer and is not a qualification of its EOF handling.
- The previous managed backend retained the JSON restore repair but had the
  adapter removed. Peer EOF reproduced a 5.224-second forced kill without its
  unload hook; the next normal stop completed in about 0.214 seconds. The
  report explicitly marks this as an expected regression and not a qualified
  compatibility pass.

Each stop retains its console and hash, recorded process identities, parent-only
signal, actual forced-kill count and unload-hook completion. Recorded descendants
disappeared and an unrelated sibling survived in all cases. The strict positive
gate requires less than five seconds, no forced kill, the unload hook, completed
loader shutdown, no selected shutdown errors and clean recorded child exits.
The generic console collector still sets its diagnostic
`cleanShutdownVerified` to false; the plugin-specific lifecycle gate supplies
the stronger assertions. The repaired and original-source consoles each retain
one unattributed JSON diagnostic. No blanket error-free console claim is made.

Independent checks reconstructed the prior restore repair from the published
ZIP, verified all other archive members, and compared the installed native
backend/helper hashes. The shared adapter is unchanged. Main's other 36 native
dispatch bodies, other 33 native cases, other 115 catalog rows and all 116
status/install policies are preserved. Existing managed copies need
Update/reinstall for the new receipt requirement. Compatibility remains
**partial**: Steam library-tab editing still has no library/MobX target.

The full server suite passed 1942 tests in 246.931 seconds with
16 skips. Website tests passed 18 tests with no skips. One production
HTTP/SSH installer method passed across 37 pinned fixtures, including TabMaster's
receipt, installed backend bytes and removal. It does not execute official
backends or replace the full e2e/catalog suite. All owned installer containers,
volumes, networks and image tags were removed and their absence checked.
Native container/image cleanup remains bound to the frozen runner; native
process cleanup is audited independently.

[Structured audit](framey-tabmaster-ipc-eof-2026-10-31.json) and
[raw reports, failure, consoles, test logs and verifiers](framey-tabmaster-ipc-eof-2026-10-31-raw.json.gz)
retain the results and all 16 native source fingerprints. The full native matrix
was not repeated locally. Exact-head hosted CI/e2e, native AMD64/ARM64, ownership,
PC, every triggered package mode, current-main CI, feedback, mergeability and
integration gates remain required. This scoped local result does not qualify
#520's earlier head; it needs integration and revalidation with this repair.
No new browser/backend integration, Steam CEF, library-tab editing, real Frame,
wearer/controller or release proof was obtained. No headset or hourly schedule
was touched.
