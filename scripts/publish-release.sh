#!/bin/sh
# Publish a tested draft release so running copies of Frame Control offer it
# (docs/releasing.md). Checks every installer is attached with a SHA-256
# digest first, since the app's updater refuses assets without one, then
# attaches update.json, the manifest the updater reads.
# Usage: scripts/publish-release.sh [--dry-run] v0.4.0
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
expected="Frame-Control-mac-arm64.dmg Frame-Control-mac-arm64.zip Frame-Control-Setup-x64.exe
Frame-Control-win-x64.zip Frame-Control-linux-x86_64.AppImage Frame-Control-linux-arm64.AppImage
Frame-Control-linux-amd64.deb Frame-Control-linux-arm64.deb"
page="https://github.com/$repo/releases/tag/$tag"

version=$(sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' "$(dirname "$0")/../app/package.json")
[ "v$version" = "$tag" ] || echo "note: app/package.json here says $version (the release was built from the tag)"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# Publishing sets tag_name; if the tag didn't exist GitHub would create it on
# the default branch, which isn't what was built and tested.
gh api "repos/$repo/git/ref/tags/$tag" >/dev/null 2>&1 \
  || { echo "tag $tag isn't on GitHub; push it first (git push origin $tag)" >&2; exit 1; }

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
    print("note: %s is already published; refreshing update.json and marking it latest" % tag, file=sys.stderr)
json.dump(r, sys.stdout)
EOF
id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$tmp/release.json")
echo "release  $id ($(python3 -c 'import json,sys; r=json.load(open(sys.argv[1])); print(("draft" if r["draft"] else "published") + ", tag_name " + str(r["tag_name"]))' "$tmp/release.json"))"

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
  echo "dry run: would PATCH release $id: tag_name=$tag draft=false prerelease=false make_latest=true"
  exit 0
fi

for asset in $old; do
  gh api -X DELETE "repos/$repo/releases/assets/$asset" >/dev/null
done
gh api -X POST "https://uploads.github.com/repos/$repo/releases/$id/assets?name=update.json" \
  -H "Content-Type: application/json" --input "$tmp/update.json" >/dev/null
echo "ok       update.json"

gh api -X PATCH "repos/$repo/releases/$id" -f tag_name="$tag" -F draft=false -F prerelease=false \
  -f make_latest=true --jq '"published " + .tag_name + " at " + .html_url'
echo "running copies will offer $tag at their next check"
