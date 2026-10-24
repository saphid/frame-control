# Recording and Steam clips

Frame Control can record what the headset shows, with its sound, and save it as
an `.mp4` on your computer. It can also export the clips and background
recordings from Steam's own game recording, at any length, as one `.mp4` each.
Both are on **Tools → Capture & Live**. Everything is saved to
`~/Videos/SteamFrame`, next to the screenshots in `~/Pictures/SteamFrame`.
Nothing needs installing on the computer or on the Frame: the work is done by
the `ffmpeg` that SteamOS ships.

**Recording is tested on a headset; Steam clip export isn't yet.** On a Frame
running SteamOS 0.5.6 (build 20261015.6141207), Record and Stop saved an
8-second 1080p H.264 recording with AAC sound to the computer, Stop took about a
second, and nothing was left running or stored on the Frame. That Frame had no
Steam recordings, so the clip list came back empty and export has only been
tested with files in Steam's format made by `ffmpeg`. The parts we're least sure
of are listed under [What hasn't been checked](#what-hasnt-been-checked).

## Record

Press **Record** next to **Live**. The button turns into **Stop**, and a line
under the viewer counts the time. Press **Stop**: the recording is finished on
the Frame, converted to `.mp4` there (without re-encoding) and copied to
`~/Videos/SteamFrame/rec-<date>-<time>.mp4`. The line says when it's saved.

- **What's in it**: the same picture as **Live**, SteamVR's copy of the headset
  view (one undistorted 1920×1080 eye, from `/dev/video99`), at 30 fps and
  8 Mbit/s, encoded with x264 (the Frame's hardware encoder crashes `ffmpeg`).
  The sound is what the headset plays: the monitor of PipeWire's default
  output, read through its PulseAudio server (`-f pulse -i @DEFAULT_MONITOR@`).
  The microphone isn't recorded.
- **Without sound**: before each recording Frame Control checks for a fraction
  of a second that `ffmpeg` can read that audio. If it can't, the recording goes
  ahead as video only, and the page and the saved message say so.
- **Limits**: a recording stops by itself after 20 minutes and is saved as if
  you'd pressed Stop. It needs about 2.9 GB free on the Frame to start (room for
  a full-length recording twice, while it's converted), and checks the space on
  your computer before copying. One recording runs at a time.
- **Where it waits on the Frame**: `~/.cache/frame-control/video/`, not `/tmp`,
  which is a RAM disk on SteamOS. It's deleted once copied.
- **If the connection drops or the app quits** while recording, the Frame
  stops `ffmpeg` cleanly when the SSH channel closes: it types `q` into
  `ffmpeg`'s input, as at its keyboard, and kills it if it's still there 10
  seconds later. Not a signal: SteamOS's `ffmpeg` 7.0 catches SIGTERM and
  SIGINT and carries on recording. A recording that was never copied is
  deleted when the next one starts.

Recording and **Live** can run together; both read the same device.

## Steam clips

**Steam clips** lists what Steam's game recording has kept on the Frame: saved
clips and background recordings, newest first, with the game, length and size.
**Export** joins one into a single `.mp4` in `~/Videos/SteamFrame`, named after
its folder (for example `clip_620_20261020_202134.mp4`), however long it is.
Steam's own export is reported to stop at about 60 seconds. Exports run in the
background; ones already on your computer are marked.

How it works: Steam keeps each recording as MPEG-DASH segments, one folder per
recording session.

```
~/.local/share/Steam/userdata/<account>/gamerecordings/
  video/bg_<appid>_<YYYYMMDD>_<HHMMSS>/                 background recording
  clips/clip_<appid>_<YYYYMMDD>_<HHMMSS>/video/bg_<...>/ a saved clip
      session.mpd
      init-stream0.m4s  chunk-stream0-00001.m4s  chunk-stream0-00002.m4s ...
      init-stream1.m4s  chunk-stream1-00001.m4s ...
```

Each stream's `init-stream` segment followed by its chunks, in number order, is
a playable fragmented MP4 of that stream. On the Frame, `ui/frame_clips.py`
builds those files and has `ffmpeg` put the video and audio into one `.mp4`
with `-c copy`, so nothing is re-encoded and it takes seconds. The result is
copied to the computer and deleted from the Frame. The export needs free space
on the Frame of about twice the recording's size while it runs.

The listing doesn't rely on the folder names: any folder under `clips/` or
`video/` (up to four levels down) holding `init-stream*.m4s` counts. A stream
missing its init segment or its chunks is left out. Missing chunk numbers are
shown as "pieces missing"; the rest still exports.

## Copying new ones automatically

**Settings → Copy to this computer** copies new screenshots and Steam clips
here on their own. It's off until you turn it on, with a switch each for
screenshots and Steam clips. While a headset is connected, Frame Control looks
about once a minute and copies what's new with the same code as **Save** and
**Export**: screenshots to `~/Pictures/SteamFrame`, clips to
`~/Videos/SteamFrame`.

- **Only what's new.** It copies what you take after turning it on, so the
  shots and clips already on the headset don't all arrive at once. **Copy
  everything now** copies everything that isn't on this computer yet, once.
- **Deleted stays deleted.** What it has copied is remembered, per headset, in
  `auto-sync.json` in Frame Control's data folder, so a file you delete here
  isn't copied again (**Copy everything now** would bring it back).
- **Saved clips only.** Steam's background recording is a rolling buffer, not
  something you chose to keep, so it isn't copied; export it by hand. A clip
  Steam wrote to in the last 30 seconds is still being saved and waits for the
  next look.
- **It gives way.** It waits while an install, an export, a recording or
  anything else is running on the headset, and stops between files if one
  starts. While a copy is running, switching headsets waits for it, as it does
  for an export. When the headset can't be reached it waits longer each time,
  up to 15 minutes, and starts over once it answers.
- **When this computer is full** (under 512 MB free, or a copy runs out of
  space) it pauses and says so in Settings and above the lists. Free some space
  and press **Resume**.
- **With several headsets** it copies from the one you're connected to.

Settings shows when it last checked, how many files it last copied and when,
and the last problem it had. The screenshot and clip lists say when it's on.

## For developers

`ui/frame_clips.py` holds the logic, so other features can reuse it (automatic
copying, in `ui/frame_autosync.py`, does):

- `list_clips(run_frame)` and `export_clip(id, run_frame, run, fetch)` are the
  computer's side; the server passes how to reach the Frame.
- `list_recordings(userdata)` and `export(userdata, id)` are the Frame's side,
  run as `python3 - list` / `python3 - export ID` with the file on stdin.
- `Recorder` runs one recording from Start to the copy.
- `parse_id` checks a clip id (`<account>/<clips|video>/<folder>...`, plain
  names only, no `.` or `..`) before it reaches a path or a shell.

The API, with the same guards as every other request:

| Request | Does |
|---|---|
| `GET /api/record` | The recording's state: `idle`, `starting`, `recording` (with `elapsed`, `audio`, `limit`), `stopping`, `saving`, `saved` (with `file`) or `failed` (with `error`) |
| `POST /api/record {"action": "start"\|"stop"}` | Start or stop |
| `GET /api/clips` | Steam's recordings on the Frame, each with `saved` |
| `POST /api/clips/export {"id"}` | Starts an export; poll `/api/job` |
| `POST /api/open {"what": "videos"}` | Opens `~/Videos/SteamFrame` |
| `GET /api/autosync` | Automatic copying: `screenshots`, `clips`, `since` (the watermark), `checked`, `copied`, `copied_time`, `error`, `paused`, `waiting` (clips still being written) |
| `POST /api/autosync {"action": "settings", "screenshots", "clips"}` | Turn either on or off; turning it on sets `since` to now |
| `POST /api/autosync {"action": "now"\|"resume"}` | Copy everything not here yet, once; or resume after running out of space |

They aren't available when the server runs on the Frame itself (the iPhone
app), since they save to a computer.

Tests: `tests/test_clips.py`, and `tests/test_autosync.py` for automatic
copying (with a fake headset). They run the recording's shell under bash with a
stand-in `ffmpeg`, so Stop, the time limit and the clean-up are tested as they
run on the Frame. Where `ffmpeg` is installed, they also make a 65-second DASH
recording with Steam's file names and export it with the real `ffmpeg`.

## What hasn't been checked

The 2026-10-24 read-only clip list on build `20261015.6141207` again returned
zero clips: its `gamerecordings` directory held only `gamerecording.pb`. No
Steam recording was created during that check, so a real Steam clip export is
still unverified. The recording and Stop path were verified earlier on that
build, as described above. Remaining checks:

- Audio and video sync. Both inputs are stamped with the wall clock, because
  the camera device and the audio server otherwise count from different clocks.
- The exact layout of `gamerecordings` on the Frame's SteamOS build, and
  whether a clip's segments start mid-recording. The parser is deliberately
  loose about the layout.
- How much x264 at 1080p30 costs the Frame while a game is running.
- Automatic copying: that 30 seconds without a write is a safe sign Steam has
  finished saving a clip, and how a once-a-minute listing feels on the Frame.
