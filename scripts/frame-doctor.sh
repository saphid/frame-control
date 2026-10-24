#!/usr/bin/env bash
# Read-only diagnostics, repair plans and explicit local before/after reports; see docs/frame-doctor.md.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
exec python3 "$root/scripts/frame_doctor.py" "$@"
