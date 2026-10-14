#!/usr/bin/env zsh
# Mac-side: the APK Store in the headset. Frame Control's Android catalogue
# (the same rated F-Droid list, Install, Open and Remove) as its own floating
# panel on the Steam Frame, so you can browse and install apps from inside.
# See docs/apks.md → "The store in the headset".
#
# Frame Control's server runs on the Frame itself (FRAME_LOCAL=1, as the iPhone
# app runs it) on the Frame's loopback, and Chromium opens ui/store.html as a
# panel. Installs then download and verify the APK on the Frame; the Mac isn't
# needed after `open`.
#
# Usage:
#   scripts/store-on-frame.sh open     # copy the server over if it changed, start it, open the panel
#   scripts/store-on-frame.sh close    # close the panel and stop the server
#   scripts/store-on-frame.sh status
set -euo pipefail

FRAME_ALIAS=${FRAME_ALIAS:-frame}
HERE=${0:A:h}
ROOT=${HERE:h}
PORT=47812           # the Frame's 127.0.0.1 only
APPID=2001947812     # the panel's id (panel-on-frame.sh's range)
# Not ~/.cache/frame-control: the iPhone app prunes other versions there.
REMOTE=.local/share/frame-control/store-server

cmd=${1:-}

# Same bundle the iPhone app copies (ios/scripts/make_frame_bundle.py), so the
# server on the Frame has exactly the files the desktop app ships.
deploy() {
  local tmp version
  tmp=$(mktemp -d)
  trap "rm -rf ${(q)tmp}" EXIT
  version=$(python3 "$ROOT/ios/scripts/make_frame_bundle.py" "$tmp/bundle.tar.gz")
  if ! ssh "$FRAME_ALIAS" "test -f $REMOTE/$version/ui/server.py"; then
    print -u2 "==> Copying Frame Control ($version) to the Frame"
    ssh "$FRAME_ALIAS" "set -e; mkdir -p $REMOTE; cd $REMOTE; rm -rf $version.tmp; mkdir $version.tmp
      tar xzf - -C $version.tmp; rm -rf $version; mv $version.tmp $version" <"$tmp/bundle.tar.gz"
  fi
  # Older versions, unless a server is still running from one.
  ssh "$FRAME_ALIAS" "cd $REMOTE && for d in */; do d=\${d%/}; [ \"\$d\" = $version ] && continue
    pgrep -f \"\$PWD/\$d/\" >/dev/null && continue; rm -rf -- \"\$d\"; done"
  print -r -- "$version"
}

# Runs on the Frame. Args: dir port appid key
OPEN=$(cat <<'EOF'
set -u
dir=$HOME/$1 port=$2 appid=$3 key=$4
export DISPLAY=:0 LC_ALL=C.UTF-8
unset WAYLAND_DISPLAY
xprop -root GAMESCOPE_FOCUSABLE_WINDOWS >/dev/null 2>&1 || { echo "The headset isn't showing anything (gamescope's :0 isn't up). Wake it and try again." >&2; exit 2; }
if [ -x "$HOME/chromium-xr/chrome" ]; then
  # Steam's overlay library crashes Chromium's zygote (docs/webxr-chromium.md).
  browser=(env LD_PRELOAD= "$HOME/chromium-xr/chrome" --user-data-dir="$HOME/.local/share/frame-control/store")
elif flatpak info org.chromium.Chromium >/dev/null 2>&1; then
  browser=(flatpak run org.chromium.Chromium --user-data-dir="$HOME/.var/app/org.chromium.Chromium/frame-store")
else
  echo "The store needs a Chromium on the Frame: Chromium XR (docs/webxr-chromium.md) or the org.chromium.Chromium Flatpak (scripts/install-apps.sh)." >&2
  exit 3
fi
# A fresh server each time, so it runs this version with this key.
[ -f /tmp/frame-store-server.pid ] && kill "$(cat /tmp/frame-store-server.pid)" 2>/dev/null
# Match the browser by its profile flag and the server by its script path: this
# launcher's own command line holds the bundle path, so a looser pattern kills it.
pkill -f '[-]-user-data-dir=[^ ]*/(frame-control/store|frame-store) ' || true
pkill -f '[s]tore-server/[^/ ]*/ui/server[.]py' || true
sleep 0.5
cd "$dir" || exit 1
FRAME_LOCAL=1 FRAME_UI_KEY=$key FRAME_DEVICE=headset setsid nohup python3 -I -u -B "$dir/ui/server.py" --port "$port" \
  >/tmp/frame-store-server.log 2>&1 </dev/null &
echo $! > /tmp/frame-store-server.pid
up=
for _ in $(seq 1 40); do
  curl -s -o /dev/null "http://127.0.0.1:$port/store" && { up=1; break; }
  sleep 0.25
done
[ -n "$up" ] || { echo "Frame Control's server didn't start on the Frame:" >&2; tail -n 15 /tmp/frame-store-server.log >&2; exit 1; }
setsid nohup "${browser[@]}" --ozone-platform=x11 --force-device-scale-factor=1 --no-first-run --no-default-browser-check \
  --password-store=basic --disable-session-crashed-bubble --noerrdialogs --disable-infobars \
  --disable-features=Translate,MediaRouter --window-size=1280,800 \
  "--app=http://127.0.0.1:$port/store?key=$key" >/tmp/frame-store.log 2>&1 </dev/null &
# Tag the window so it's its own panel (docs/panels.md).
for _ in $(seq 1 60); do
  sleep 0.5
  for win in $(xwininfo -root -children 2>/dev/null | awk '/^ +0x/ {print $1}'); do
    xprop -id "$win" _NET_WM_NAME WM_NAME 2>/dev/null | grep -qF "APK Store" || continue
    if xprop -id "$win" -f STEAM_GAME 32c -set STEAM_GAME "$appid" 2>/dev/null; then
      echo "panel valve.steam.desktopgame.$appid window $win"
      exit 0
    fi
  done
done
echo "Chromium started, but its window didn't appear within 30 s:" >&2
tail -n 15 /tmp/frame-store.log >&2
exit 1
EOF
)

case "$cmd" in
  open)
    version=$(deploy | tail -n 1)
    key=$(openssl rand -hex 16)
    ssh "$FRAME_ALIAS" bash -s -- "$REMOTE/$version" "$PORT" "$APPID" "$key" <<<"$OPEN"
    ;;
  close)
    ssh "$FRAME_ALIAS" 'pkill -f "[-]-user-data-dir=[^ ]*/(frame-control/store|frame-store) " || true
      pkill -f "[s]tore-server/[^/ ]*/ui/server[.]py" || true
      [ -f /tmp/frame-store-server.pid ] && kill "$(cat /tmp/frame-store-server.pid)" 2>/dev/null; rm -f /tmp/frame-store-server.pid; true'
    ;;
  status)
    ssh "$FRAME_ALIAS" "ls $REMOTE 2>/dev/null; curl -s -o /dev/null http://127.0.0.1:$PORT/store && echo 'server up' || echo 'server down'
      pgrep -af '[-]-user-data-dir=[^ ]*/(frame-control/store|frame-store) |[s]tore-server/[^/ ]*/ui/server[.]py' | head -n 1 | cut -c1-120"
    ;;
  *) sed -n '2,15p' "$0"; exit 2 ;;
esac
