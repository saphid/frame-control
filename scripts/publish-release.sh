#!/bin/sh
# Publish a tested draft release so running copies of Frame Control offer it
# (docs/releasing.md). Checks every installer is attached with a SHA-256
# digest first, since the app's updater refuses assets without one, then
# attaches update.json, the manifest the updater reads.
# Usage: FRAME_SMOKE_RESULT=/path/to/result.json RELEASE_ASSET_AUDIT=/path/to/audit.json \
#        scripts/publish-release.sh [--dry-run] v0.4.0
#
# Everything goes through the REST API (gh api), not `gh release view/edit`:
# those look a draft up by its tag, and a draft can show tag_name
# "untagged-..." until it's published, so they report "release not found"
# (and GraphQL is often rate-limited). A draft's html_url is an untagged-...
# link that dies on publishing, so update.json's page is built from the tag.
set -eu
dry=""
[ "${1:-}" = "--dry-run" ] && { dry=1; shift; }
tag="${1:?usage: $0 [--dry-run] vX.Y.Z}"
repo=saphid/frame-control
checkout=$(CDPATH= cd "$(dirname "$0")/.." && pwd -P)
expected="Frame-Control-mac-arm64.dmg Frame-Control-mac-arm64.zip Frame-Control-mac-x64.dmg Frame-Control-mac-x64.zip Frame-Control-Setup-x64.exe
Frame-Control-win-x64.zip Frame-Control-linux-x86_64.AppImage Frame-Control-linux-arm64.AppImage
Frame-Control-linux-amd64.deb Frame-Control-linux-arm64.deb"
page="https://github.com/$repo/releases/tag/$tag"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# Publishing sets tag_name; if the tag didn't exist GitHub would create it on
# the default branch, which isn't what was built and tested.
gh api "repos/$repo/git/ref/tags/$tag" >/dev/null 2>&1 \
  || { echo "tag $tag isn't on GitHub; push it first (git push origin $tag)" >&2; exit 1; }

# A complete asset list is insufficient: a cancelled installer build can leave
# old uploaded bytes behind. Check the exact tagged commit's main/e2e jobs and
# every exact-tag push run and attempt before any release mutation.
gate_output=$(python3 "$(dirname "$0")/verify-release-gates.py" "$tag" "${FRAME_SMOKE_RESULT:-}")
printf '%s\n' "$gate_output"
release_commit=$(printf '%s\n' "$gate_output" | sed -n 's/^exact release commit: \([0-9a-f]\{40\}\)$/\1/p')
[ -n "$release_commit" ] || { echo "not publishing: release gate did not report an exact commit" >&2; exit 1; }
local_commit=$(git -C "$checkout" rev-parse --verify HEAD) || {
  echo "not publishing: publisher is not running from a git checkout" >&2; exit 1;
}
[ "$local_commit" = "$release_commit" ] || {
  echo "not publishing: local checkout $local_commit differs from release commit $release_commit" >&2; exit 1;
}
local_status=$(git -C "$checkout" status --porcelain --untracked-files=normal) || {
  echo "not publishing: could not inspect local release checkout" >&2; exit 1;
}
[ -z "$local_status" ] || {
  echo "not publishing: local release checkout has uncommitted or untracked files" >&2; exit 1;
}
version=$(git -C "$checkout" show HEAD:app/package.json | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])') || {
  echo "not publishing: could not read the release commit package version" >&2; exit 1;
}
[ "v$version" = "$tag" ] || {
  echo "not publishing: release commit package version $version differs from $tag" >&2; exit 1;
}

# Every release, drafts included, one JSON object per line.
gh api --paginate "repos/$repo/releases?per_page=100" --jq '.[]' > "$tmp/releases"
# The release whose tag_name is the tag; failing that, the one untagged-... draft
# titled "Frame Control X.Y.Z" (release.yml's title), optionally ": subtitle".
python3 - "$tag" "$tmp/releases" > "$tmp/release.json" <<'EOF'
import json, re, sys
tag, path = sys.argv[1], sys.argv[2]
rels = [json.loads(line) for line in open(path) if line.strip()]
hits = [r for r in rels if r.get("tag_name") == tag]
if not hits:
    # Exactly this version: "Frame Control 0.4.0", or that followed by ": <subtitle>".
    # Never "Frame Control 0.4.0-rc.1" or "0.4.00", and only drafts with no real tag.
    title = re.compile(r"Frame Control " + re.escape(tag.lstrip("v")) + r"(: .*)?", re.S)
    hits = [r for r in rels if r.get("draft") and str(r.get("tag_name") or "").startswith("untagged-")
            and title.fullmatch(r.get("name") or "")]
if len(hits) != 1:
    why = "no release" if not hits else "%d releases (ids %s)" % (len(hits), ", ".join(str(r["id"]) for r in hits))
    sys.exit("found %s for %s; expected one draft" % (why, tag))
r = hits[0]
if not r.get("draft"):
    sys.exit("not publishing: %s is already published; leave its live update manifest intact" % tag)
json.dump(r, sys.stdout)
EOF
id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$tmp/release.json")
echo "release  $id ($(python3 -c 'import json,sys; r=json.load(open(sys.argv[1])); print(("draft" if r["draft"] else "published") + ", tag_name " + str(r["tag_name"]))' "$tmp/release.json"))"
python3 - "$tmp/release.json" <<'EOF'
import json, sys
release = json.load(open(sys.argv[1]))
if (release.get("body") or "").lstrip().startswith("> **WITHDRAWN"):
    sys.exit("not publishing: this release is marked WITHDRAWN")
EOF

missing=""
for name in $expected; do
  digest=$(python3 -c 'import json,sys
d=json.load(open(sys.argv[1])); n=sys.argv[2]
print(next((a.get("digest") or "" for a in d["assets"] if a["name"]==n), "absent"))' "$tmp/release.json" "$name")
  case "$digest" in
    sha256:*) echo "ok       $name" ;;
    absent) echo "MISSING  $name"; missing=1 ;;
    *) echo "NO HASH  $name"; missing=1 ;;
  esac
done
[ -z "$missing" ] || { echo "not publishing: fix the assets above" >&2; exit 1; }

# The workflow uploads this only after all ten platform builds complete.
# Regenerate it from GitHub's installer digests and compare its own GitHub
# digest, so a stale or partial checksum file cannot pass the release gate.
python3 "$(dirname "$0")/release-checksums.py" < "$tmp/release.json" > "$tmp/SHA256SUMS"
expected_sum=$(sha256sum "$tmp/SHA256SUMS" | cut -d ' ' -f 1)
checksum_digest=$(python3 -c 'import json,sys
d=json.load(open(sys.argv[1])); matches=[a.get("digest") for a in d["assets"] if a["name"]=="SHA256SUMS"]
print(matches[0] if len(matches)==1 else "absent")' "$tmp/release.json")
[ "$checksum_digest" = "sha256:$expected_sum" ] || {
  echo "not publishing: SHA256SUMS is absent or does not match the ten installer digests" >&2; exit 1;
}
echo "ok       SHA256SUMS"

[ -n "${RELEASE_ASSET_AUDIT:-}" ] || {
  echo "not publishing: RELEASE_ASSET_AUDIT is required from the independent installer audit" >&2
  exit 1
}
python3 "$(dirname "$0")/verify-release-asset-audit.py" "$RELEASE_ASSET_AUDIT" "$tmp/release.json" "$tag"

# Every published release carries the same concrete verification instructions.
# Keep the release's own notes, and append this section only once. The tag URL
# is stable even while a draft temporarily has an untagged-* API name.
python3 - "$tmp/release.json" "$(dirname "$0")/release-safety-note.md" "$tag" > "$tmp/release-with-note.json" <<'EOF'
import json, pathlib, sys
d = json.load(open(sys.argv[1]))
body = (d.get("body") or "").rstrip()
if "## Is it safe?" not in body:
    note = pathlib.Path(sys.argv[2]).read_text(encoding="utf-8").replace("{tag}", sys.argv[3]).strip()
    body = (body + "\n\n" if body else "") + note
d["body"] = body
json.dump(d, sys.stdout)
EOF
mv "$tmp/release-with-note.json" "$tmp/release.json"
python3 - "$tmp/release.json" > "$tmp/release-body.txt" <<'EOF'
import json, sys
sys.stdout.buffer.write(json.load(open(sys.argv[1]))["body"].encode("utf-8"))
EOF

# update.json: what running copies read (app/updater.js), from github.com's
# latest/download link rather than the rate-limited REST API.
python3 - "$tmp/release.json" "$tag" "$page" "$expected" > "$tmp/update.json" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))
tag, page, names = sys.argv[2], sys.argv[3], set(sys.argv[4].split())
print(json.dumps({"version": tag.lstrip("v"), "page": page, "notes": (d.get("body") or "")[:4000],
                  "assets": [{"name": a["name"], "size": a["size"], "digest": a["digest"]}
                             for a in d["assets"] if a["name"] in names]}, indent=1))
EOF
old=$(python3 -c 'import json,sys
d=json.load(open(sys.argv[1]))
print(" ".join(str(a["id"]) for a in d["assets"] if a["name"]=="update.json"))' "$tmp/release.json")

if [ -n "$dry" ]; then
  echo "dry run: would replace update.json (old asset ids: ${old:-none}) with:"
  cat "$tmp/update.json"
  echo "dry run: would include the Is it safe? section in the release body"
  echo "dry run: would PATCH release $id: tag_name=$tag draft=false prerelease=false make_latest=true"
  exit 0
fi

for asset in $old; do
  gh api -X DELETE "repos/$repo/releases/assets/$asset" >/dev/null
done
gh api -X POST "https://uploads.github.com/repos/$repo/releases/$id/assets?name=update.json" \
  -H "Content-Type: application/json" --input "$tmp/update.json" > "$tmp/uploaded-manifest.json"
asset_id=$(python3 - "$tmp/uploaded-manifest.json" "$tmp/update.json" <<'EOF'
import hashlib, json, pathlib, sys
asset = json.load(open(sys.argv[1], encoding="utf-8"))
body = pathlib.Path(sys.argv[2]).read_bytes()
digest = "sha256:" + hashlib.sha256(body).hexdigest()
if (asset.get("name") != "update.json" or not isinstance(asset.get("id"), int)
        or asset["id"] <= 0 or asset.get("size") != len(body)
        or asset.get("digest") != digest):
    sys.exit("not publishing: uploaded update.json metadata differs from its source bytes")
print(asset["id"])
EOF
)
gh api -H "Accept: application/octet-stream" "repos/$repo/releases/assets/$asset_id" > "$tmp/update-readback.json"
cmp -s "$tmp/update.json" "$tmp/update-readback.json" || {
  echo "not publishing: downloaded update.json differs from its source bytes" >&2; exit 1;
}
echo "ok       update.json"

gh api -X PATCH "repos/$repo/releases/$id" -f tag_name="$tag" -f body="$(cat "$tmp/release-body.txt")" -F draft=false -F prerelease=false \
  -f make_latest=true --jq '"published " + .tag_name + " at " + .html_url'
echo "running copies will offer $tag at their next check"
