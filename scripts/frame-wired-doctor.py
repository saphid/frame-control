#!/usr/bin/env python3
"""Source-checkout entry point for the PC's read-only USB-C route checks."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'ui'))
from frame_wired_doctor import main  # noqa: E402

if __name__ == '__main__':
    raise SystemExit(main())
