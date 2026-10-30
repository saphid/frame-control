#!/usr/bin/env bash
# Linux or Mac with Docker: the Frame simulator, a fake Steam Frame on this
# computer for trying Frame Control without the headset. It is the e2e tests'
# fake Frame (tests/fakeframe) plus stand-ins for SteamVR, the headset view and
# the proximity sensor (tests/fakeframe/sim), kept running on 127.0.0.1 under
# the SSH alias `frame-sim`, so the app, the scripts and the smoke test can all
# use it like a headset. See docs/testing.md.
#
# Usage: scripts/frame-sim.sh COMMAND
#   up                  build (if needed) and start it; writes the frame-sim alias
#   down [--forget]     stop it; --forget also drops its volumes, alias and host key
#   status              is it up, and the fake's state
#   ctl ARGS...         fault switches: fakeframe-ctl's (pairing, sleep, battery, ...)
#                       plus vr on|off and worn on|off; `ctl help` lists them
#   ssh [COMMAND...]    ssh into it as steamos
#   run COMMAND...      run a command with FRAME_ALIAS=frame-sim, e.g. run scripts/push.sh
#   smoke [ARGS...]     the headset smoke test against it (results in tests/smoke/results-sim)
#   ui                  start ui/server.py against it on port 47811
#   logs                its logs, and the fake's per-service logs
#
# Env: FRAME_SIM_SSH_PORT (2222), FRAME_SIM_DEVKIT_PORT (32000), FRAME_SIM_CTL_PORT (9999),
#      FRAME_SIM_ALIAS (frame-sim), FAKEFRAME_BASE (base image, as scripts/e2e.sh)
set -euo pipefail

root=$(CDPATH= cd "$(dirname "$0")/.." && pwd -P)
alias_name=${FRAME_SIM_ALIAS:-frame-sim}
export FRAME_SIM_SSH_PORT=${FRAME_SIM_SSH_PORT:-2222}
export FRAME_SIM_DEVKIT_PORT=${FRAME_SIM_DEVKIT_PORT:-32000}
export FRAME_SIM_CTL_PORT=${FRAME_SIM_CTL_PORT:-9999}
ssh_dir=${FRAME_CONTROL_SSH_DIR:-$HOME/.ssh}
key=$ssh_dir/id_ed25519_frame          # Frame Control's own key (ui/frame_connect.py KEY)
export FRAME_SIM_PUBKEY=$key.pub
compose=(docker compose -p frame-sim -f "$root/tests/fakeframe/sim/compose.yaml")
known_host="[127.0.0.1]:$FRAME_SIM_SSH_PORT"

say() { printf '%s\n' "$*"; }
die() { printf 'frame-sim: %s\n' "$*" >&2; exit 1; }
usage() { sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; }

need_docker() {
  command -v docker >/dev/null || die "needs Docker (on a Mac: brew install colima docker && colima start)"
  docker info >/dev/null 2>&1 || die "Docker isn't running, or this user can't use it"
}

running() { [ "$(docker inspect -f '{{.State.Running}}' frame-sim 2>/dev/null)" = true ]; }
need_running() { running || die "not running; start it with: scripts/frame-sim.sh up"; }

build() {
  local base
  case $(uname -m) in
    x86_64|amd64) base=archlinux:base ;;
    aarch64|arm64) base=registry.gitlab.steamos.cloud/holo/holo-core-aarch64-preview/base-devel:latest ;;
    *) die "no Arch Linux base image known for $(uname -m); set FAKEFRAME_BASE" ;;
  esac
  base=${FAKEFRAME_BASE:-$base}
  # Both every time: cached layers make it quick, and changes under tests/fakeframe are picked up.
  say "==> Building the fake Frame (fakeframe-frame, from $base)"
  docker build -q --build-arg BASE="$base" -t fakeframe-frame \
    -f "$root/tests/fakeframe/Containerfile" "$root/tests/fakeframe" >/dev/null 2>&1 \
    || docker build --build-arg BASE="$base" -t fakeframe-frame \
      -f "$root/tests/fakeframe/Containerfile" "$root/tests/fakeframe" \
    || die "the fake Frame image didn't build"
  say "==> Building the simulator (frame-sim)"
  docker build -q -t frame-sim -f "$root/tests/fakeframe/sim/Containerfile" "$root/tests/fakeframe/sim" >/dev/null 2>&1 \
    || docker build -t frame-sim -f "$root/tests/fakeframe/sim/Containerfile" "$root/tests/fakeframe/sim" \
    || die "the simulator image didn't build"
}

# The alias as Frame Control's own setup writes it (frame_connect.write_config), so
# the app's Devices list shows the simulator like any other headset.
write_alias() {
  FRAME_CONTROL_SSH_DIR=$ssh_dir PYTHONPATH="$root/ui" python3 - "$alias_name" "$FRAME_SIM_SSH_PORT" <<'PY'
import platform, sys
import frame_connect as fc
fc.use_alias(sys.argv[1])
fc.make_ssh_dir()
fc.make_key(fc.KEY, "ed25519", f"{platform.node() or 'computer'}->steam-frame")
fc.make_key(fc.DEVKIT_KEY, "rsa", fc.key_comment(platform.node()))
fc.write_config("127.0.0.1", int(sys.argv[2]))
PY
}

# Frame Control pins each headset's host key in its own file, named by the app's
# device id (frame_devices.known_hosts). `pin forget` drops the simulator's; `pin
# renew` replaces it with the key just put in known_hosts, as the app's own
# seed_pin does, so a recreated simulator needs no "trust this key" step.
pin() {
  FRAME_CONTROL_SSH_DIR=$ssh_dir PYTHONPATH="$root/ui" python3 - "$1" "$alias_name" "$FRAME_SIM_SSH_PORT" <<'PY' || true
import sys
import frame_devices as fd
action, alias, port = sys.argv[1], sys.argv[2], int(sys.argv[3])
device = fd.Registry().by_alias(alias)
if device:
    fd.forget_pin(device["id"])
    if action == "renew":
        fd.seed_pin(device["id"], ["127.0.0.1"], port)
PY
}

forget_alias() {
  FRAME_CONTROL_SSH_DIR=$ssh_dir PYTHONPATH="$root/ui" python3 - "$alias_name" <<'PY' || true
import sys
import frame_devices
frame_devices.remove_block(sys.argv[1])
PY
  ssh-keygen -R "$known_host" -f "$ssh_dir/known_hosts" >/dev/null 2>&1 || true
  pin forget
}

# Trust the simulator's host key. It lives in a volume, so it only changes after
# `down --forget`; then the old entry is replaced rather than refused.
trust_host_key() {
  local scanned=""
  for _ in $(seq 1 60); do
    scanned=$(ssh-keyscan -T 2 -p "$FRAME_SIM_SSH_PORT" 127.0.0.1 2>/dev/null | sed "s/^127\.0\.0\.1 /[127.0.0.1]:$FRAME_SIM_SSH_PORT /") || true
    [ -n "$scanned" ] && break
    sleep 1
  done
  [ -n "$scanned" ] || die "its sshd didn't answer on 127.0.0.1:$FRAME_SIM_SSH_PORT"
  touch "$ssh_dir/known_hosts"
  if ! printf '%s\n' "$scanned" | awk '{print $2, $3}' | while read -r kind blob; do
      grep -qF "$known_host $kind $blob" "$ssh_dir/known_hosts" || exit 1
    done; then
    ssh-keygen -R "$known_host" -f "$ssh_dir/known_hosts" >/dev/null 2>&1 || true
    printf '%s\n' "$scanned" >> "$ssh_dir/known_hosts"
    pin renew
  fi
}

cmd_up() {
  need_docker
  build
  write_alias
  [ -s "$FRAME_SIM_PUBKEY" ] || die "no $FRAME_SIM_PUBKEY"
  say "==> Starting the simulator"
  "${compose[@]}" up -d --wait >/dev/null || { "${compose[@]}" logs --tail 60 frame; die "it didn't come up"; }
  trust_host_key
  ssh -o BatchMode=yes -o ConnectTimeout=10 "$alias_name" true \
    || die "it's up, but 'ssh $alias_name' doesn't log in"
  say "==> Up. A fake Steam Frame on 127.0.0.1:$FRAME_SIM_SSH_PORT, SSH alias '$alias_name'."
  say "    ssh $alias_name                          # a shell on it"
  say "    scripts/frame-sim.sh ui                  # Frame Control against it (or pick '$alias_name' in the app's Devices)"
  say "    scripts/frame-sim.sh run scripts/push.sh # any script, with FRAME_ALIAS=$alias_name"
  say "    scripts/frame-sim.sh ctl help            # faults: asleep, battery, pairing, worn, ..."
}

cmd_down() {
  need_docker
  if [ "${1:-}" = --forget ]; then
    "${compose[@]}" down -v --remove-orphans
    forget_alias
    say "==> Stopped; its volumes, the '$alias_name' alias and its host key are gone"
  else
    "${compose[@]}" down --remove-orphans
    say "==> Stopped (scripts/frame-sim.sh up starts it again with the same host key)"
  fi
}

cmd_ctl() {
  need_running
  case ${1:-help} in
    vr|worn) docker exec frame-sim frame-sim-ctl "$@" ;;
    help)
      docker exec frame-sim fakeframe-ctl help
      say "  vr on|off                   SteamVR running: vrcmd, headset view, live view (simulator)"
      say "  worn on|off                 someone wearing it: activity level, proximity (simulator)" ;;
    *) docker exec frame-sim fakeframe-ctl "$@" ;;
  esac
}

cmd_status() {
  need_docker
  if ! running; then
    say "frame-sim: not running"
    exit 1
  fi
  say "frame-sim: up on 127.0.0.1:$FRAME_SIM_SSH_PORT (alias $alias_name)"
  docker exec frame-sim fakeframe-ctl ping
  docker exec frame-sim frame-sim-ctl state
}

case ${1:-} in
  up) shift; cmd_up "$@" ;;
  down) shift; cmd_down "$@" ;;
  status) cmd_status ;;
  ctl) shift; cmd_ctl "$@" ;;
  ssh) shift; need_running; exec ssh "$alias_name" "$@" ;;
  run) shift; [ $# -gt 0 ] || die "run what?"; need_running; FRAME_ALIAS=$alias_name exec "$@" ;;
  smoke)
    shift; need_running
    # Its own folder: a simulator run is never evidence about a headset (and
    # verify-frame-smoke-result.py refuses one marked simulated).
    FRAME_ALIAS=$alias_name FRAME_SMOKE_RESULTS=${FRAME_SMOKE_RESULTS:-$root/tests/smoke/results-sim} \
      exec "$root/scripts/frame-smoke.sh" "$@" ;;
  ui)
    shift; need_running
    say "==> Frame Control against $alias_name: http://127.0.0.1:${PORT:-47811}/"
    FRAME_ALIAS=$alias_name exec python3 "$root/ui/server.py" --port "${PORT:-47811}" "$@" ;;
  logs)
    need_running
    docker logs --tail 80 frame-sim
    docker exec frame-sim sh -c 'for f in /var/log/fakeframe/*.log; do echo "--- $f"; tail -n 40 "$f"; done' ;;
  -h|--help|help|"") usage ;;
  *) usage >&2; exit 2 ;;
esac
