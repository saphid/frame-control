#!/usr/bin/env python3
"""Print SHA256SUMS for the ten release installers from GitHub asset metadata.

GitHub computes each asset digest from its uploaded bytes. The workflow runs
this only after all platform builds finish; publish-release.sh checks that the
uploaded SHA256SUMS bytes still match these digests before publishing.
"""
import argparse
import json
import re
import sys

INSTALLERS = (
    "Frame-Control-mac-arm64.dmg",
    "Frame-Control-mac-arm64.zip",
    "Frame-Control-mac-x64.dmg", "Frame-Control-mac-x64.zip",
    "Frame-Control-Setup-x64.exe",
    "Frame-Control-win-x64.zip",
    "Frame-Control-linux-x86_64.AppImage",
    "Frame-Control-linux-arm64.AppImage",
    "Frame-Control-linux-amd64.deb",
    "Frame-Control-linux-arm64.deb",
)


def find_release(lines, tag):
    releases = [json.loads(line) for line in lines if line.strip()]
    hits = [r for r in releases if r.get("tag_name") == tag]
    if not hits:
        title = re.compile(r"Frame Control " + re.escape(tag.removeprefix("v")) + r"(: .*)?")
        hits = [r for r in releases if r.get("draft")
                and str(r.get("tag_name") or "").startswith("untagged-")
                and title.fullmatch(r.get("name") or "")]
    if len(hits) != 1:
        raise ValueError(f"expected one release for {tag}; found {len(hits)}")
    return hits[0]


def checksums(release):
    assets = release.get("assets") or []
    lines = []
    for name in INSTALLERS:
        matches = [a for a in assets if a.get("name") == name]
        if len(matches) != 1:
            raise ValueError(f"expected one asset named {name}; found {len(matches)}")
        digest = matches[0].get("digest") or ""
        if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
            raise ValueError(f"missing SHA-256 digest for {name}")
        lines.append(f"{digest[7:].lower()}  {name}")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="find exact release in JSON-lines input")
    parser.add_argument("--id", action="store_true", help="print the selected release id")
    args = parser.parse_args()
    data = sys.stdin.read()
    release = find_release(data.splitlines(), args.tag) if args.tag else json.loads(data)
    if args.id:
        print(int(release["id"]))
    else:
        # Windows text stdout changes LF to CRLF. SHA256SUMS must have the same
        # bytes on every runner, including publish-release.sh's verification.
        sys.stdout.buffer.write(checksums(release).encode("ascii"))


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        sys.exit(str(exc))
