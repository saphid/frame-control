#!/usr/bin/env bash
# Read-only setup and health diagnostics; see docs/frame-doctor.md.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
exec python3 "$root/scripts/frame_doctor.py" "$@"
