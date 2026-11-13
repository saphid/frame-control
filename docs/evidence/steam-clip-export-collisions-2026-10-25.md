# Steam clip export collision fixtures, 25 October 2026

Base: `d79efb4` (Frame Control v0.4.30). Issue:
[#212](https://github.com/saphid/frame-control/issues/212).
Host: Linux 6.8.0-139-generic, Python 3.12.3, ffmpeg 6.1.1.

## Baseline reproduction

Loaded the unmodified `ui/frame_clips.py` from `d79efb4` into a temporary
Python module and exported three fake sources into a temporary directory:

```
1/clips/clip_620/video/bg
2/clips/clip_620/video/bg
1/clips/clip_620/video/other
```

Each source's payload was its own ID. All three exports returned the same
destination, `clip_620.mp4`; listing marked all three saved. The final file
contained only the last source ID. No SSH or headset was used.

## Regression coverage

`tests/test_clips.py` exports five IDs on each of two fake headsets, including
equal clip names across accounts, nested sessions with equal leaf names,
different leaf names under one clip and the background/clip distinction.
All ten payloads survive at distinct destinations. Listing marks only the
identities already exported. A pre-existing flat MP4 retains its original
bytes and does not mark any identity saved. Normal export still returns
`message` and `file`, removes its remote temporary export and clears local
staging; a failed re-export preserves the completed file.

`tests/test_clip_copy.py` exercises the server's list and manual export
functions and its actual auto-sync callbacks with fake transport. A manual
copy is recognised by auto-sync, all other account/session identities copy,
and switching to a second headset copies its own sources without overwriting
the first. A delayed manual job refuses a changed headset with status 409.
Both local phone mode and local headset runtime reject Steam clip list,
export and auto-sync requests with status 400. The separate `Recorder` path
is unchanged.

## Validation

- `PYTHONPATH=tests python3 -m unittest test_clips test_clip_copy test_autosync test_shot_copy test_headset_actions -v`
  — 66 tests passed in 17.288 seconds, no skips. Includes real ffmpeg/ffprobe
  export of a generated 65-second DASH fixture and recording stop/cleanup.
- `PYTHONPATH=tests python3 -m unittest test_server -v`
  — 44 tests passed in 12.315 seconds, no skips.
- `node --test site/test/*.test.mjs` — 2 tests passed.
- `python3 -m unittest discover -s tests -v` — 1,518 tests run in
  181.025 seconds; OK, 16 skipped for unavailable platform/tool prerequisites.
- `python3 -m py_compile ui/frame_clips.py ui/server.py tests/test_clips.py tests/test_clip_copy.py`
  and `git diff --check` — passed.

The server and full Python suites require localhost sockets and were run
outside the network sandbox. Tests import `tests/sandbox.py` to isolate app
data, SSH settings, home directories and service URLs.

## Limits and upgrade behaviour

No real headset was accessed: the shared device lock is held by other work.
This is Linux fixture and server coverage, not a fresh packaged-app or
Windows/macOS verification. Existing real-headset export evidence in the
recording guide predates this destination change.

Old flat exports cannot prove headset/account/session identity and are left
untouched. Previously remembered auto-sync IDs retain their existing
watermark/history behaviour; **Copy everything now** or manual **Export**
creates an identified copy. No release, version bump, merge or social post
is included. PR #113 is outside this task.
