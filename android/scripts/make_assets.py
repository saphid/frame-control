#!/usr/bin/env python3
"""Use the same reproducible headset bundle as the iPhone app."""
import pathlib
import subprocess
import sys

root = pathlib.Path(__file__).resolve().parents[2]
out = pathlib.Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=True)
version = subprocess.check_output(
    [sys.executable, str(root / 'ios/scripts/make_frame_bundle.py'),
     str(out / 'frame-bundle.tar.gz')], cwd=root, text=True).strip().splitlines()[-1]
(out / 'frame-bundle.version').write_text(version + '\n')
