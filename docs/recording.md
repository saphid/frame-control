# Recording and Steam clips

Frame Control can record what the headset shows, with its sound, and save it as
an `.mp4` on your computer. It can also export the clips and background
recordings from Steam's own game recording, at any length, as one `.mp4` each.
Both are on **Tools → Capture & Live**. Everything is saved to
`~/Videos/SteamFrame`, next to the screenshots in `~/Pictures/SteamFrame`.
Nothing needs installing on the computer or on the Frame: the work is done by
the `ffmpeg` that SteamOS ships.

**Not tested on a headset yet.** This is built from what the code already does
on the Frame (the live view, the media player) and from how Steam is reported
to store its recordings. The parts we're least sure of are listed under
[What hasn't been checked](#what-hasnt-been-checked). Please report what you see.

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
  stops `ffmpeg` cleanly when the SSH channel closes, as the live view does. A
  recording that was never copied is deleted when the next one starts.

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

## For developers

`ui/frame_clips.py` holds the logic, so other features (such as syncing clips
automatically) can reuse it:

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

They aren't available when the server runs on the Frame itself (the iPhone
app), since they save to a computer.

Tests: `tests/test_clips.py`. They run the recording's shell under bash with a
stand-in `ffmpeg`, so Stop, the time limit and the clean-up are tested as they
run on the Frame. Where `ffmpeg` is installed, they also make a 65-second DASH
recording with Steam's file names and export it with the real `ffmpeg`.

## What hasn't been checked

None of this has run on a Steam Frame yet. In particular:

- That SteamOS's `ffmpeg` can read `@DEFAULT_MONITOR@`. It has the PulseAudio
  output device (the media player plays through it), so the input is expected,
  but if it fails the recording is video only, as above.
- Audio and video sync. Both inputs are stamped with the wall clock, because
  the camera device and the audio server otherwise count from different clocks.
- The exact layout of `gamerecordings` on the Frame's SteamOS build, and
  whether a clip's segments start mid-recording. The parser is deliberately
  loose about the layout.
- How much x264 at 1080p30 costs the Frame while a game is running.
