# Screenshot Save on a real Frame, 25 October 2026

After PR #192 merged, Frame Control's production `list_shots()` and
`save_shots()` paths were run from lxso2 against the real Frame. The test held
the shared `/tmp/frame-test.lock` with an owner marker and removed only its own
lock. A separate locked check earlier in this round found SteamVR at activity
level 3 (standby). No new screenshot was created.

- The Frame listed seven existing Steam screenshots.
- One existing screenshot was copied to a temporary folder on the PC. Its
  local size matched the reported remote size: **294,885 bytes**. The new
  destination had four components below the temporary root: headset, Steam
  account, game ID and filename.
- Saving the same screenshot a second time returned zero new copies. A fresh
  list then marked that screenshot as saved.
- The temporary PC folder and its private image were removed at the end. The
  source screenshot on the Frame was only read. Battery was **100% Full**
  before and after.

This verifies one real screenshot transfer and the repeat-save behavior. It
does **not** reproduce two different real screenshots with the same filename;
the account/game/headset collision case is covered by the fake-source test in
`tests/test_shot_copy.py`. Windows and macOS physical-PC saves were not tested.
Active passthrough in the recording mirror remains unknown because the Frame
was in standby.
