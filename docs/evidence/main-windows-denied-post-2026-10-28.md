# Main Windows test gate, 28 October 2026

Exact main commit `b5bbcec1a0cc3f8b3d25ef2686fd8315e209f167`
([checks run 40723931638](https://github.com/saphid/frame-control/actions/runs/40723931638))
failed in `server-tests (windows-latest, 3.12)`. Its server test step had one
error: `test_settings_need_and_accept_the_ui_key` received Windows
`ConnectionAbortedError [WinError 10053]` while reading an unauthorized
POST response. The test sent a JSON body, but the missing-key guard rejects
the request before reading it. Closing a connection with an unread body can
reset it on Windows; that is the likely cause, rather than a settings write
failure. The other Windows tests completed, and the exact-main native Decky
runtime run passed.

The test now sends an empty POST when checking that a missing key is refused.
Its subsequent authorized POST still sends a settings body and verifies the
saved value. The local `tests/test_server.py` module passed 45 tests after
this change. Hosted Windows CI on the repair commit and green exact-main CI
remain required before further merges.
