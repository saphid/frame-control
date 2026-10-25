#!/bin/sh
# Mac or Linux: the headset smoke test. Installs, launches and removes tiny
# test titles on the Frame (the `frame` alias) and records the results with
# its BUILD_ID under tests/smoke/results/. See docs/testing.md.
#
# Usage: scripts/frame-smoke.sh [--pair]   (--pair needs you in the headset to approve)
set -eu
smoke_root=$(CDPATH= cd "$(dirname "$0")/.." && pwd -P)
exec python3 "$smoke_root/tests/smoke/frame_smoke.py" "$@"
