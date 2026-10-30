#!/usr/bin/env python3
"""What the simulated headset "shows": a synthetic two-eye picture for the headset
view, live view and recordings. It is a test pattern, not a render of anything.

  scene.py screenshot STEREO.png PREVIEW.png   one frame, as SteamVR's stereo screenshot
  scene.py graph FPS                           the lavfi source graph the ffmpeg wrapper streams
  scene.py text                                rewrite screen.txt (title, battery, clock) now

Each eye is 960x1080 side by side (1920x1080), the size frame_vrshot.py saw on the
Frame (2026-09-25, SteamVR 2.17.10). The right eye is shifted a little so the
picture reads as stereo.
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simstate as ss  # noqa: E402

FFMPEG = '/usr/bin/ffmpeg'
FONT = '/usr/share/fonts/TTF/DejaVuSans.ttf'


def text():
    title = ss.running_title()
    battery = ss.fs.read()['battery']
    lines = ['FRAME SIMULATOR', 'not a real headset', '',
             f'Playing: {title}' if title else 'Steam home',
             f"Battery {battery['capacity']}% {battery['status']}",
             time.strftime('%H:%M:%S')]
    tmp = ss.SCREEN_TEXT + f'.{os.getpid()}.tmp'
    with open(tmp, 'w') as f:
        f.write('\n'.join(lines))
    os.chmod(tmp, 0o666)
    os.replace(tmp, ss.SCREEN_TEXT)     # drawtext reload=1 reads whole files only


def graph(fps):
    # drawtext's textfile with expansion=none: the text needs no escaping and "%" stays "%".
    return (f"color=c=0x0e1621:s=1000x1080:r={fps},"
            "drawgrid=w=100:h=100:t=2:c=0x1a9fff@0.25,"
            "drawbox=x='420+260*sin(t*1.3)':y='700+90*cos(t)':w=160:h=160:c=0x66c0f4@0.9:t=fill,"
            f"drawtext=fontfile={FONT}:textfile={ss.SCREEN_TEXT}:reload=1:expansion=none:"
            "fontcolor=white:fontsize=38:line_spacing=16:x=110:y=260,"
            "split[a][b];[a]crop=960:1080:40:0[l];[b]crop=960:1080:0:0[r];[l][r]hstack")


def screenshot(stereo, preview):
    text()
    common = [FFMPEG, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y', '-f', 'lavfi', '-i', graph(30)]
    # The stereo file first and the left-eye preview last, as the compositor writes them.
    subprocess.run(common + ['-frames:v', '1', '-f', 'image2', '-c:v', 'png', stereo + '.tmp'], check=True)
    os.replace(stereo + '.tmp', stereo)
    subprocess.run([FFMPEG, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y', '-i', stereo,
                    '-vf', 'crop=960:1080:0:0', '-f', 'image2', '-c:v', 'png', preview + '.tmp'], check=True)
    os.replace(preview + '.tmp', preview)


def main(argv):
    if argv[:1] == ['screenshot'] and len(argv) == 3:
        screenshot(argv[1], argv[2])
    elif argv[:1] == ['graph'] and len(argv) == 2:
        print(graph(int(argv[1])))
    elif argv == ['text']:
        text()
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
