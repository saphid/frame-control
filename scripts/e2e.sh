#!/usr/bin/env zsh
# Linux host with Docker: run the end-to-end tests against the fake Frame.
# Builds the fake Frame and host images (tests/fakeframe), starts them with
# docker compose, runs tests/e2e in the host container, prints the results
# and takes everything down again. Exits with the tests' status (2 if the
# harness itself didn't come up). See docs/testing.md.
#
# Usage: scripts/e2e.sh [TEST...]     e.g. scripts/e2e.sh test_titles test_faults.Faults.test_disk_full
# Env:   FAKEFRAME_BASE   base image (default: archlinux:base, or Valve's Holo Core aarch64 on arm64)
#        FAKEFRAME_KEEP=1 leave the containers running afterwards
#        FRAMEY_AUDIT_CACHE  host directory containing exact catalog ZIPs (read-only)
#        FRAMEY_AUDIT_OUTPUT host result JSON to copy out after the full suite
set -uo pipefail

root=${0:A:h:h}
cd "$root" || exit 2
case $(uname -m) in
  x86_64|amd64) base=archlinux:base ;;
  aarch64|arm64) base=registry.gitlab.steamos.cloud/holo/holo-core-aarch64-preview/base-devel:latest ;;
  *) print -u2 "No Arch Linux base image known for $(uname -m); set FAKEFRAME_BASE"; exit 2 ;;
esac
base=${FAKEFRAME_BASE:-$base}
compose=(docker compose -p fakeframe-e2e -f tests/fakeframe/compose.yaml)
catalog_override=''
if [[ -n ${FRAMEY_AUDIT_OUTPUT:-} && -z ${FRAMEY_AUDIT_CACHE:-} ]]; then
  print -u2 'FRAMEY_AUDIT_OUTPUT requires FRAMEY_AUDIT_CACHE'
  exit 2
fi
started=$SECONDS

print "==> Building fakeframe-frame (from $base) and fakeframe-host"
# Quiet when it works; if a build fails, build again with the full log so CI shows why.
# That second build also rides out a flaky package mirror: only its failure is fatal.
build() { docker build -q "$@" >/dev/null || docker build --progress=plain "$@" || exit 2 }
build --build-arg BASE="$base" -t fakeframe-frame -f tests/fakeframe/Containerfile tests/fakeframe
build -t fakeframe-host -f tests/fakeframe/host.Containerfile tests/fakeframe

logs() {
  print "\n==> Fake Frame logs"
  $compose logs --no-color --tail 80 fakeframe
  $compose exec -T fakeframe sh -c 'for f in /var/log/fakeframe/*.log; do echo "--- $f"; tail -n 40 "$f"; done' 2>/dev/null
  print "\n==> ui/server.py log"
  $compose exec -T host sh -c 'tail -n 80 /tmp/fakeframe-e2e-server.log' 2>/dev/null
}

finish() {
  if [[ ${FAKEFRAME_KEEP:-0} == 1 ]]; then
    print "==> Left running: ${(j: :)compose} exec host bash"
  else
    $compose down -v --remove-orphans >/dev/null 2>&1
  fi
  [[ -z $catalog_override ]] || rm -f -- "$catalog_override"
}
trap finish EXIT

if [[ -n ${FRAMEY_AUDIT_CACHE:-} ]]; then
  catalog_override=$(mktemp "${TMPDIR:-/tmp}/framey-catalog-compose.XXXXXXXX.json") || exit 2
  python3 - "$FRAMEY_AUDIT_CACHE" "$catalog_override" <<'PY' || exit 2
import json, pathlib, sys
cache = pathlib.Path(sys.argv[1]).resolve(strict=True)
if not cache.is_dir():
    raise SystemExit('FRAMEY_AUDIT_CACHE must be a directory')
pathlib.Path(sys.argv[2]).write_text(json.dumps({'services': {'host': {
    'volumes': [{'type': 'bind', 'source': str(cache), 'target': '/audit-cache', 'read_only': True}],
    'environment': {'FRAMEY_AUDIT_CACHE': '/audit-cache'}}}}))
PY
  compose+=(-f "$catalog_override")
fi

$compose down -v --remove-orphans >/dev/null 2>&1
print "==> Starting the fake Frame and the host"
if ! $compose up -d --wait; then
  logs
  exit 2
fi
print "==> Up after $(( SECONDS - started )) s; running tests/e2e"

if (( $# )); then
  args=(-v "$@")
else
  args=(discover -v -s .)
fi
tests_started=$SECONDS
$compose exec -T -w /repo/tests/e2e host python3 -m unittest "${args[@]}"
rc=$?
if [[ -n ${FRAMEY_AUDIT_OUTPUT:-} ]]; then
  mkdir -p -- "${FRAMEY_AUDIT_OUTPUT:A:h}" || exit 2
  # Copy even a partial result after a failure. A successful suite must produce
  # its catalog result; otherwise a missing mount/accidental skip cannot pass.
  if ! $compose cp host:/tmp/framey-catalog-result.json "$FRAMEY_AUDIT_OUTPUT"; then
    (( rc != 0 )) || rc=2
  fi
fi
(( rc == 0 )) || logs
print "\n==> tests/e2e: $([[ $rc == 0 ]] && echo passed || echo "FAILED (exit $rc)") in $(( SECONDS - tests_started )) s" \
      "($(( SECONDS - started )) s with builds)"
exit $rc
