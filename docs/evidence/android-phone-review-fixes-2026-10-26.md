# Android phone companion: review fixes (2026-10-26)

Base: `ae9df354`. This evidence covers fixes for seven findings from an
independent review of the Android companion (issue #108).

## Status of earlier evidence

The APK, emulator and physical-device evidence in
`android-phone-screenshot-sync-2026-10-24.md` was captured from `ae9df354`.
It is **historical**. It does not show that the fixes below work on a device.
No emulator, phone or headset was used for the initial implementation round.
Later parent verification is recorded below.

## What changed

| Finding | Fix | Covered by |
| --- | --- | --- |
| F1 Stop could leave an ongoing notification or wrong status | `SessionGate` gives each service instance one session token, so an ended session cannot post status, page or notification updates. `SyncEngine.close()` stops all writes before a new session opens the library. `onDestroy` also cancels notification 108. | `SessionGateTest` (4), `closedEngineCannotWriteAfterAnotherEngineTakesOver` |
| F2 Pairing could merge a key into an unterminated last line | `FrameConnection.authorizeCommand` uses the same newline guard as the iPhone app. | `FrameConnectionTest` runs the generated shell against a temporary HOME |
| F3 Every 4-second poll rewrote and fsynced the journal | `reconcile` commits only when a receipt or the account set changes. | 3 tests that turn any journal write into a failure |
| F4 One empty or over-30 MiB file blocked every listing | Out-of-range sizes are skipped for that poll only. Unsafe ids, non-finite times and conflicting duplicates still reject the whole listing. | `emptyOrOversizedFiles…` |
| F5 The screen parsed, and could write, the journal on the UI thread | `SyncEngine.snapshot` is a read-only view. The screen loads it on a background thread, drops results for a headset that is no longer paired, and clears the list when the pairing changes. | `readOnlySnapshotNeverCreatesUpgradesOrRewrites`; existing native `changingHeadsetsRebindsShareToTheSelectedOriginal` compiles |
| F6 An opt-out after an interrupted export left a hidden pending row | `GalleryExporter.discardPending` removes this app's pending rows in `Pictures/Frame Control/` when Gallery is turned off, and again when sync starts with Gallery off. Published rows are kept. | Native `optOutDiscardsInterruptedPendingRowsButKeepsPublishedImages` (compiled, not run) |
| F7 Missing userdata, or a new account, could import its history | Each Steam account gets its own baseline. The app lists the account folders over SSH, so an account with no screenshots yet still counts as established. Version 1 journals upgrade to version 2 and trust only the accounts they already have receipts for. `ui/server.py` is unchanged. | 6 JVM tests plus `accountListingSeparatesAbsentUserdataFromEmptyAccounts` |

Nonblocking items: the workflow's `push` trigger is now `main` only, and the
docs and app text now say that a locked phone can delay transfers.

## Verification

Command (JDK 17, Android SDK platform 36):

```sh
./android/gradlew -p android clean assembleDebug testDebugUnitTest assembleDebugAndroidTest lintDebug --no-daemon
```

- Exit 0. There are 53 JVM tests (34 before), all passing, none skipped.
- Lint reports 0 errors and 12 warnings. All 12 are pre-existing kinds (version hints, i18n, WebView JavaScript).
- Mutation check: restoring the old unconditional commit and the old key append made 4 tests fail.
- `app-debug.apk` SHA-256: `e4a1f498fef6fbc9919ccb4077b8e15b609caea6a2192d3f1bd2b13ea78bcb15`
- `app-debug-androidTest.apk` SHA-256: `f9acb6bc002665cff6a31d0aaf2d528f4b1eaaaa82ead9fb383867e1154f6053`

## Round 2: fixes for the independent Sol review

An independent review (GPT-6.1 Sol, high reasoning) of the fixes above found two
product defects and one test timing defect. All three are addressed below.

| Finding | Fix | Covered by |
| --- | --- | --- |
| R1 A Gallery change before the first poll on a version 1 journal wrote an unreadable journal | A setting-only write now keeps the journal's version, so a version 1 journal stays a valid version 1 journal. Only the first poll upgrades it, and it writes version 2 and the account set together. The baseline policy is unchanged. | JVM `versionOneJournalStaysValidWhenGalleryChangesBeforeFirstPoll` (constructor and toggle paths, immediate reopen and snapshot, then the upgrade). Native `galleryOptOutLatchesPreviouslyPairedLibraries` now includes a retained version 1 library. |
| R2 After Stop, a late export from the old session could delete the Gallery image that the next session had just saved | `GalleryExporter.EXPORTS` is one process-wide lock. Each export holds it from the row lookup through publish or cancellation, across exporter instances and sessions. It is taken before the settings lock and never while holding it. The wait is interruptible and limited to 30 seconds. After that, the item fails for this poll and is retried. | Native `stoppedSessionExportCannotDeleteNextSessionsGalleryImage`. A JVM harness outside the repository runs the real exporter and engine with an in-memory resolver: with the lock, 10 of 10 runs keep the image; with the lock removed, 10 of 10 runs lose it. |
| R3 The headset-switch share test assumed the background library load had finished | The test waits, up to a time limit, until the expected original is shareable. It accepts no button while a library loads. It then checks that only one share button remains and that it shares the new headset's original. | `changingHeadsetsRebindsShareToTheSelectedOriginal` |

The parent's first native run (API 36, APK `e4a1f498…`) ran 5 tests: 4 passed.
`optOutDiscardsInterruptedPendingRowsButKeepsPublishedImages` reached and
passed its assertions, then its cleanup threw `SecurityException` deleting a
row the product had already removed. The test now drops that row from cleanup
after it proves the row is gone.

The parent also ran the account-listing command read-only against the real
headset. It exited 0 and listed one account. That is not proof of the phone's
download pipeline.

Round 2 verification (same command, JDK 17, platform 36):

- Exit 0. There are 54 JVM tests, all passing: `SyncEngineTest` 47, `SessionGateTest` 4, `FrameConnectionTest` 3.
- Lint reports 0 errors and 12 warnings, the same pre-existing kinds as round 1.
- Mutation check for R1: removing the version-preserving line made only the new R1 test fail, with the invalid version 2 header the review described.
- Two clean builds gave the same hashes. They replace the round-1 APKs:
  - `app-debug.apk` SHA-256: `139443c8f3246527ed629731b4f2a099939a2ba7590b628cde415f3f0d7ab996`
  - `app-debug-androidTest.apk` SHA-256: `3a84246a7b40436fd5fc521154541603050805270e21e052e26b31a5fa1e0cc2`

## Parent verification of the round-2 APKs

The parent installed both round-2 APKs above on the isolated API 36 emulator
and ran the six non-live instrumentation methods explicitly. All six passed,
none skipped; the supervisor exited 0. This includes actual MediaStore
round-trip and retry, retained version 1 library opt-out, asynchronous
headset-switch sharing, hidden pending-row removal, and the FIFO-controlled
Stop/restart export overlap. The chooser was intercepted; no original was
sent to another app.

The native overlap test exercised real MediaProvider rows: after both old and
new exporters finished, the successor's image remained published with matching
original bytes. This verifies the overlap mechanism, rather than a complete
service Stop/restart against a live headset.

The parent also checked the 54 passing JVM XML results, the build's recorded
exit 0, whitespace, and both APK hashes. Native output and sanitized metadata
are in `android-phone-review-fixes-2026-10-26/` beside this document.

## Not verified

- API 29 runtime behavior and physical Android locked/Doze behavior remain unverified.
- The account-listing command ran against the real headset; the final phone download pipeline and password-pairing UI have not been rerun against it.
- A complete service Stop/restart during a live headset download is not proven by the exporter overlap test.
- iOS APNs delivery, physical locked-phone Photos export, production signing, and release remain open.
