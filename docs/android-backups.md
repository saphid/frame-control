# Import an Android game backup

A SideQuest backup can contain a small APK and much larger `main.…obb` and
`patch.…obb` files. All of them belong to the same game. Installing only the APK
can leave the game unable to start because its assets are missing.

In **Android → Import game files…**, choose the APK and its OBB files together.
You can also drop them anywhere in the window. In the desktop app, dropping the
APK alone finds matching OBB files beside it; dropping a folder containing the
APK and OBBs also works. Browsers can read only the files you explicitly choose.

The import screen shows the game app and its game-data files together. **Import
game & data** installs the APK, starts its own Steam library instance, waits for
Android and the installed package, copies the OBBs, and closes the game. Open it
again from the Steam library to play. The screen explains this before import;
choosing files alone never starts a game.

Files are matched using the package inside the APK and the standard
`main|patch.<version>.<package>.obb` name, not the APK's filename. Both main and
patch files are preserved. OBB version numbers need not equal the APK's current
version code: updates can reuse older expansion files. The copy uses the existing
SHA-256 transfer check inside Android and writes to that game's own
`/sdcard/Android/obb/<package>` folder.

If no data files are selected, the screen reminds you to include any OBBs in the
backup before offering **Install game app**. An APK cannot reliably tell Frame
Control whether separate expansion files are required. Game-data files are never
silently sent to Downloads by this flow.

If setup fails, the import screen keeps the error and retry instructions visible.
The APK may already be installed, but the game is not reported ready. Import the
same backup again, or choose just its OBB files to add data to an existing install.
The importer checks the installed package and version before writing data and
closes the instance after a failed copy. Unrelated or duplicate files, running
games that would be replaced, and downgrades are rejected. Uploaded staging files
are discarded after use or cancellation; abandoned imports expire after an hour
when the importer is next used, and dead-server staging folders are swept at
startup.

This flow handles one ordinary APK and standard OBB files for one game at a time.
Split APKs, XAPK/APKS archives, nested Android/data folders and private save
archives need their own import handling. PC ZIP/folder/EXE imports keep their
existing route. Quest USB and Meta library imports keep their existing workflow.

Validation covers actual APK parsing, the three-file backup layout, package
matching, sibling discovery, browser upload staging and cleanup, instance/version
guards and failure recovery with mocked headset operations. Browser verification
uses the real page and upload/inspection endpoints with simulated installation.
**Verified 2026-10-20 on a real Steam Frame**, BUILD_ID `20260925.6191901`:
F-Droid Basic 2.0.2 with two synthetic main/patch OBBs completed the automatic
install/start/copy/close sequence. Reopening its persistent instance confirmed
both SHA-256 hashes in `/sdcard/Android/obb/org.fdroid.basic`. The test app,
shortcut and instance were removed afterward, the shared device lock was
released, and the battery remained at 99%. See [device evidence](evidence/android-import/device.json).
The headset was unworn; this checks transfer and persistence, not rendering,
Resident Evil 4 gameplay, or a game that exits before data can be copied. This
flow does not change APK compatibility or remove licence checks.
