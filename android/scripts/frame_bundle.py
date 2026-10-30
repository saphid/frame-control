#!/usr/bin/env python3
"""Pack the headset server for the Android app from committed files only.

`git archive REV` goes to a private snapshot, and that snapshot's own
ios/scripts/make_frame_bundle.py packs it, so the archive is byte for byte what
the iPhone build makes from a clean checkout of REV. Nothing is read from the
working tree, so uncommitted or untracked files can't get in.

Usage: frame_bundle.py --repo DIR --rev COMMIT --out OUT.tar.gz
                       [--expect-sha256 HEX] [--provenance OUT.json]
Prints the archive's SHA-256.
"""
import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

PACKER = "ios/scripts/make_frame_bundle.py"


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout


def snapshot(repo, rev, dest):
    data = git(repo, "archive", "--format=tar", rev)
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        for member in tar.getmembers():
            name = Path(member.name)
            if name.is_absolute() or ".." in name.parts or not (member.isfile() or member.isdir() or member.issym()):
                sys.exit(f"refusing archive entry {member.name!r}")
        if hasattr(tarfile, "data_filter"):
            tar.extractall(dest, filter="data")
        else:
            tar.extractall(dest)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--rev", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--expect-sha256")
    ap.add_argument("--provenance", type=Path)
    args = ap.parse_args()

    if not re.fullmatch(r"[0-9a-f]{40}", args.rev):
        sys.exit("--rev must be a full 40-character commit hash")
    commit = git(args.repo, "rev-parse", "--verify", "--end-of-options", f"{args.rev}^{{commit}}").decode().strip()
    tree = git(args.repo, "rev-parse", f"{commit}^{{tree}}").decode().strip()

    with tempfile.TemporaryDirectory(prefix="frame-bundle-") as tmp:
        snap = Path(tmp) / "src"
        snap.mkdir()
        snapshot(args.repo, commit, snap)
        packer = snap / PACKER
        out = Path(tmp) / "frame-bundle.tar.gz"
        version = subprocess.run([sys.executable, "-I", "-B", str(packer), str(out)], check=True,
                                 capture_output=True, cwd=tmp).stdout.decode().strip()
        data = out.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if version != digest[:16]:
            sys.exit(f"packer printed {version}, archive hashes to {digest}")
        if args.expect_sha256 and digest != args.expect_sha256.lower():
            sys.exit(f"bundle from {commit} is {digest}, expected {args.expect_sha256}")
        files = []
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            for m in tar.getmembers():
                if m.isfile():
                    files.append({"path": m.name, "mode": oct(m.mode), "size": m.size,
                                  "sha256": hashlib.sha256(tar.extractfile(m).read()).hexdigest()})
        provenance = {
            "repo_commit": commit,
            "repo_tree": tree,
            "packer": PACKER,
            "packer_sha256": hashlib.sha256(packer.read_bytes()).hexdigest(),
            "archive_sha256": digest,
            "archive_bytes": len(data),
            "version": version,
            "files": files,
        }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(data)
    if args.provenance:
        args.provenance.write_text(json.dumps(provenance, indent=2) + "\n")
    print(digest)


if __name__ == "__main__":
    main()
