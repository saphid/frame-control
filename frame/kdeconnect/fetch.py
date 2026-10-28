#!/usr/bin/env python3
"""Download the KDE Connect packages Frame Control ships for the Frame into
frame/kdeconnect/packages, checking each against its pinned SHA-256
(packages.json). Already-downloaded files that match are kept.

ios/scripts/make_frame_bundle.py runs this; app/build/fetch-deps.js does the same
in Node. Usage: python3 frame/kdeconnect/fetch.py
"""
import hashlib
import http.client
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGES = HERE / "packages"


def manifest():
    return json.loads((HERE / "packages.json").read_text())


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def download_verified(url, expected_sha256):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                data = response.read()
        except (OSError, http.client.HTTPException) as error:
            # GitHub release downloads occasionally close during connection or
            # transfer. Retry those failures, but fail fast on permanent HTTP errors.
            if isinstance(error, urllib.error.HTTPError) and error.code not in (408, 429) and error.code < 500:
                raise
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
            continue
        if sha256(data) != expected_sha256:
            raise SystemExit(f"checksum mismatch for {url}: {sha256(data)}")
        return data


def fetch():
    m = manifest()
    PACKAGES.mkdir(exist_ok=True)
    for p in m["packages"]:
        path = PACKAGES / p["file"]
        if path.is_file() and sha256(path.read_bytes()) == p["sha256"]:
            continue
        url = m["release"] + p["file"]
        data = download_verified(url, p["sha256"])
        tmp = path.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(path)
    wanted = {p["file"] for p in m["packages"]}
    for old in PACKAGES.iterdir():
        if old.name not in wanted:
            old.unlink()
    return [PACKAGES / p["file"] for p in m["packages"]]


if __name__ == "__main__":
    for path in fetch():
        print(path.relative_to(HERE.parent.parent), file=sys.stderr)
