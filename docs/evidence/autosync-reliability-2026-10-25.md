# Auto-sync retry and headset-selection reliability

Date: 25 October 2026. Base: `d79efb4`, Frame Control v0.4.30.
Issue: [#214](https://github.com/saphid/frame-control/issues/214).
Environment: Linux x86_64, Python 3.12.3, Node 24.15.0.

## Reproduced problems

The existing 19 auto-sync tests passed on the base revision. Added regressions
failed before the implementation: an exhausted clip lost its error, explicit
retry did not recover failed screenshots or clips, and switches around listing
or copying continued the old pass. The original callback interface also had no
way to carry the tick's captured device into the server list reservation.

The final fake-source tests exercise these boundaries:

- Fail screenshots or clips three times, keep checking without further copy
  attempts, and retain the source error plus an explicit retry instruction.
- Recover the source and use either Resume or Copy everything now without
  restarting. Successful copies stay deduplicated; Resume retains the ledger
  even after a local file is deleted. Copy everything now retains its documented
  ability to restore deleted files and include older media.
- Reset an exhausted budget while the source still fails: another three
  attempts are allowed, rather than unlimited background attempts.
- Save an exhausted item by hand and clear its stale failure on the next list.
- Switch after tick captures A, during a list, after screenshot bookkeeping,
  between media kinds, before a transfer, or before transfer bookkeeping.
  Interrupted passes do not mark the other headset's IDs or continue copying.
- Switch to B exactly at callback entry through the production `_sync_list`
  adapter. `working(A)` refuses before calling the source list, leaving both
  ledgers and copy callbacks untouched. The same production reservation blocks
  a device switch during a list and rejects stale screenshot/clip transfers.
- Execute the production Settings renderer in Node: Resume is available for
  copy errors and disk-full pauses, and hidden for a healthy state.

## Implementation boundary

Each list callback now receives the captured device, like the copy callbacks.
The existing server `working(meant)` mechanism checks that intended headset
under `_work_lock` while reserving work; `devices_post` uses the same lock to
refuse switches during that work. The worker also checks for interruption
around lists and transfers. No new device lock or clip destination logic is
introduced. The server diff is confined to `_sync_list`.

The failed-attempt and error maps are in-memory and reset on explicit retry or
restart. The successful-copy ledger and settings persistence retain their
existing format. Disk-full pauses, offline backoff, clip settling and the
three-attempt limit remain covered by the original tests.

## Checks

- `python3 -m unittest discover -s tests -p test_autosync.py -v`: 33 passed.
- `python3 -m unittest discover -s tests -p test_shot_copy.py -v`: 2 passed.
- `python3 -m unittest discover -s tests -p test_clips.py -v`: 34 passed,
  including local ffmpeg coverage.
- `python3 -m unittest discover -s tests -p test_service_regressions.py -v`:
  36 passed.
- `python3 -m unittest discover -s tests -p test_page_scripts.py -v`: 5 passed.
- `node --test site/test/*.test.mjs`: 2 test files passed.
- `python3 -m py_compile ui/frame_autosync.py ui/server.py tests/test_autosync.py`
  and `git diff --check`: passed.

- `python3 -m unittest discover -s tests -v`: 1,525 tests run in 184.876
  seconds, passed with 16 skips. Ran with sandbox escalation for loopback
  sockets; test isolation still used throwaway app/SSH data and mocked headset
  transport. Final output:

  ```text
  Ran 1525 tests in 184.876s
  OK (skipped=16)
  ```

## Limits and handoff

All new regressions use fake sources and mocked transport; they do not prove
real-headset transfer or UI rendering. No headset was accessed: its shared test
lock was held by another task. The Docker fake-Frame end-to-end suite and
Windows/macOS runs were not performed locally. The coordinator owns review and
merge; this task does not release, change PR #113, or publish announcements.
