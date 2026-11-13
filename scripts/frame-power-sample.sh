#!/usr/bin/env bash
# Read-only, bounded power/heat sampler. See docs/power-and-heat.md.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
exec python3 "$root/scripts/frame_power_sample.py" "$@"
