#!/usr/bin/env python3
"""Fetch pinned app/runtime closures, then verify and bundle them offline.

Only the bundle phase proves signatures/content. Neither phase installs an app
or touches a host Flatpak store. Local generated bundles retain the published
commit signatures; their hashes are reported, not treated as published hashes.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import configparser
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import threading

import gi
from gi.repository import Gio, GLib


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "app_fetch", ROOT / "framey-fetch-syncthing-flatpak.py"
)
fetcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetcher)
RUNTIMES = {
    "x86_64": "2bb946ea4ebb050f6a32f90e979feb975b08280d1ff1aac881dec3d1361ad84d",
    "aarch64": "c3daeced6f88f9c4ffc4f88c798c48fffd395d873fc0d36b7fc73b753d7f59c9",
}
MAX_OBJECT = 64 * 1024**2
MAX_TOTAL = 640 * 1024**2
MAX_ENTRIES = 50000


def pins(arch):
    return {"app": fetcher.payload.COMMITS[arch], "runtime": RUNTIMES[arch]}


def run(args, timeout=600):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(
            str(args) + ": " + result.stdout[-3000:] + result.stderr[-3000:]
        )
    return result.stdout


def public_key(descriptor):
    data = descriptor.read_bytes()
    if hashlib.sha256(data).hexdigest() != fetcher.payload.DESCRIPTOR_SHA256:
        raise ValueError("Unexpected original Flathub descriptor")
    configuration = configparser.ConfigParser()
    configuration.read_string(data.decode())
    key = base64.b64decode(configuration["Flatpak Repo"]["GPGKey"], validate=True)
    if hashlib.sha256(key).hexdigest() != fetcher.payload.KEY_SHA256:
        raise ValueError("Unexpected Flathub public key")
    return key


def fetch(directory, arch, seeds):
    directory.mkdir(parents=True, exist_ok=False)
    store = directory / "objects"
    store.mkdir()
    lock = threading.Lock()
    index, key_locks = {}, {}
    total = 0

    def get(checksum, kind):
        nonlocal total
        if len(checksum) != 64 or any(c not in "0123456789abcdef" for c in checksum):
            raise ValueError("Invalid checksum")
        name = checksum + "." + kind
        with lock:
            key_lock = key_locks.setdefault(name, threading.Lock())
        with key_lock:
            relative = Path(checksum[:2]) / name[2:]
            path = store / relative
            if name in index:
                return path.read_bytes()
            source = next(
                (seed / relative for seed in seeds if (seed / relative).exists()), None
            )
            if source is not None:
                if (
                    source.is_symlink()
                    or not source.is_file()
                    or source.stat().st_size > MAX_OBJECT
                ):
                    raise ValueError("Unsafe or oversized seed object")
                data = source.read_bytes()
            else:
                data = fetcher.download(
                    fetcher.BASE + "objects/" + relative.as_posix(), MAX_OBJECT
                )
            digest = hashlib.sha256(data).hexdigest()
            if kind not in ("filez", "commitmeta") and digest != checksum:
                raise ValueError("Metadata checksum mismatch")
            with lock:
                total += len(data)
                if total > MAX_TOTAL or len(index) >= MAX_ENTRIES:
                    raise ValueError("Package closure exceeds bound")
                index[name] = {"bytes": len(data), "sha256": digest}
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(data)
            return data

    report = {
        "architecture": arch,
        "commits": pins(arch),
        "payloadIntegrityVerified": False,
        "packageLaunched": False,
        "maximumObjectBytes": MAX_OBJECT,
        "maximumClosureBytes": MAX_TOTAL,
    }
    try:
        descriptor = fetcher.download(fetcher.BASE + "flathub.flatpakrepo", 1024**2)
        (directory / "flathub.flatpakrepo").write_bytes(descriptor)
        public_key(directory / "flathub.flatpakrepo")
        contents = set()
        for kind, commit in pins(arch).items():
            value = fetcher.variant(get(commit, "commit"), "(a{sv}aya(say)sstayay)")
            get(commit, "commitmeta")
            ref = (
                (
                    ("app/" + fetcher.payload.APP)
                    if kind == "app"
                    else "runtime/org.gnome.Platform"
                )
                + "/"
                + arch
                + "/"
                + ("stable" if kind == "app" else "49")
            )
            if (
                value[0]["ostree.ref-binding"] != [ref]
                or value[0]["ostree.collection-binding"] != "org.flathub.Stable"
            ):
                raise ValueError("Unexpected signed payload binding")
            pending = {(bytes(value[6]).hex(), bytes(value[7]).hex())}
            seen = set()

            def tree(pair):
                checksum, metadata = pair
                get(metadata, "dirmeta")
                files, children = fetcher.variant(
                    get(checksum, "dirtree"), "(a(say)a(sayay))"
                )
                for entry in files + children:
                    if (
                        not entry[0]
                        or entry[0] in (".", "..")
                        or "/" in entry[0]
                        or "\x00" in entry[0]
                    ):
                        raise ValueError("Invalid payload name")
                return (
                    [bytes(checksum).hex() for _, checksum in files],
                    [
                        (bytes(child).hex(), bytes(metadata).hex())
                        for _, child, metadata in children
                    ],
                )

            with ThreadPoolExecutor(max_workers=8) as pool:
                while pending:
                    current = pending - seen
                    seen.update(current)
                    pending = set()
                    for files, children in pool.map(tree, sorted(current)):
                        contents.update(files)
                        pending.update(children)
                    if len(seen) + len(pending) > 20000 or len(contents) > 30000:
                        raise ValueError("Payload traversal exceeds bound")
            report[kind + "DirectoryTrees"] = len(seen)
        with ThreadPoolExecutor(max_workers=8) as pool:
            for number, _ in enumerate(
                pool.map(lambda value: get(value, "filez"), sorted(contents)), 1
            ):
                if number % 1000 == 0:
                    print(
                        "Fetched",
                        number,
                        "/",
                        len(contents),
                        "content objects",
                        flush=True,
                    )
        report["downloadComplete"] = True
    except BaseException as error:
        report["error"] = str(error)
        raise
    finally:
        report.update(
            totalObjectBytes=total,
            fileContentObjects=len(contents) if "contents" in locals() else 0,
            objects=index,
        )
        (directory / "fetch-report.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
    return report


def bundle(directory, output, arch):
    gi.require_version("OSTree", "1.0")
    from gi.repository import OSTree

    objects = (directory / "objects").resolve()
    entries = list(objects.rglob("*"))
    if len(entries) > MAX_ENTRIES + 256:
        raise ValueError("Too many object cache entries")
    total = 0
    for path in entries:
        relative = path.relative_to(objects)
        if path.is_symlink() or len(relative.parts) > 2:
            raise ValueError("Unsafe object cache path")
        if path.is_file():
            name, separator, kind = path.name.partition(".")
            checksum = relative.parts[0] + name
            if (
                len(relative.parts) != 2
                or len(checksum) != 64
                or not separator
                or any(c not in "0123456789abcdef" for c in checksum)
                or kind not in ("commit", "commitmeta", "dirtree", "dirmeta", "filez")
            ):
                raise ValueError("Invalid cached object name")
            size = path.stat().st_size
            total += size
            if size > MAX_OBJECT or total > MAX_TOTAL:
                raise ValueError("Cached payload exceeds bound")
    output.mkdir(parents=True, exist_ok=False)
    key = output / "flathub-key.gpg"
    key.write_bytes(public_key(directory / "flathub.flatpakrepo"))
    repo = output / "repo"
    command = ["ostree", "--repo=" + str(repo)]
    run(command + ["init", "--mode=archive-z2"])
    run(
        command + ["remote", "add", "--gpg-import=" + str(key), "flathub", fetcher.BASE]
    )
    (repo / "objects").rmdir()
    (repo / "objects").symlink_to(objects, target_is_directory=True)
    repository = OSTree.Repo.new(Gio.File.new_for_path(str(repo)))
    repository.open(None)
    report = {
        "architecture": arch,
        "commits": pins(arch),
        "signatures": {},
        "bundles": {},
        "payloadIntegrityVerified": False,
        "packageInstalled": False,
        "packageLaunched": False,
        "keySha256": fetcher.payload.KEY_SHA256,
    }
    try:
        for kind, commit in pins(arch).items():
            data = (objects / commit[:2] / (commit[2:] + ".commit")).read_bytes()
            if hashlib.sha256(data).hexdigest() != commit:
                raise ValueError("Pinned commit checksum mismatch")
            value = fetcher.variant(data, "(a{sv}aya(say)sstayay)")
            name = fetcher.payload.APP if kind == "app" else "org.gnome.Platform"
            ref = (
                kind
                + "/"
                + name
                + "/"
                + arch
                + "/"
                + ("stable" if kind == "app" else "49")
            )
            if (
                value[0]["ostree.ref-binding"] != [ref]
                or value[0]["ostree.collection-binding"] != "org.flathub.Stable"
            ):
                raise ValueError("Unexpected payload ref or collection")
            verified = repository.verify_commit_for_remote(commit, "flathub", None)
            if not verified.require_valid_signature() or verified.count_valid() < 1:
                raise ValueError("No valid Flathub signature")
            report["signatures"][kind] = verified.count_valid()
            run(command + ["refs", "--create=" + ref, commit])
        report["fsck"] = run(command + ["fsck", "--all", "--verify-bindings"])
        for kind, commit in pins(arch).items():
            name = fetcher.payload.APP if kind == "app" else "org.gnome.Platform"
            target = output / (kind + ".flatpak")
            args = [
                "flatpak",
                "build-bundle",
                "--arch=" + arch,
                "--gpg-keys=" + str(key),
            ]
            if kind == "runtime":
                args.append("--runtime")
            run(
                args
                + [str(repo), str(target), name, "stable" if kind == "app" else "49"]
            )
            with target.open("rb") as source:
                digest = hashlib.file_digest(source, "sha256").hexdigest()
            report["bundles"][kind] = {
                "sha256": digest,
                "bytes": target.stat().st_size,
                "commit": commit,
            }
        report["payloadIntegrityVerified"] = True
    except BaseException as error:
        report["error"] = str(error)
        raise
    finally:
        report["sourceSha256"] = {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "framey-prepare-syncthing-flatpak.py",
                "framey-fetch-syncthing-flatpak.py",
                "framey-verify-syncthing-flatpak.py",
            )
        }
        (output / "preparation.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("fetch", "bundle"))
    parser.add_argument("--architecture", choices=tuple(RUNTIMES), required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--seed-objects", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.phase == "fetch":
        report = fetch(args.directory, args.architecture, args.seed_objects)
    else:
        if args.output is None:
            parser.error("--output is required for the offline bundle phase")
        report = bundle(args.directory, args.output, args.architecture)
    print(json.dumps({k: v for k, v in report.items() if k != "objects"}, indent=2))


if __name__ == "__main__":
    main()
