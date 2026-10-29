#!/usr/bin/env python3
"""Independently download and inspect every installer in a GitHub release.

Run on Linux after the tagged workflow finishes and before publishing its
draft. The JSON report is written only after every check passes.
"""

import argparse
import hashlib
import json
import platform
import plistlib
import re
import runpy
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


REPO = "saphid/frame-control"
SCRIPTS = Path(__file__).resolve().parent
CHECKSUMS = runpy.run_path(str(SCRIPTS / "release-checksums.py"))
INSTALLERS = CHECKSUMS["INSTALLERS"]


class AuditError(Exception):
    """Release asset metadata or downloaded bytes failed a check."""


def github_json(path):
    result = subprocess.run(
        ["gh", "api", f"repos/{REPO}/{path}"],
        capture_output=True, text=True, check=False, timeout=60,
    )
    if result.returncode:
        raise AuditError(f"GitHub read failed for {path}: {result.stderr.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise AuditError(f"invalid GitHub JSON for {path}: {error}") from error


def find_release(tag):
    releases = []
    for page in range(1, 21):
        batch = github_json(f"releases?per_page=100&page={page}")
        if not isinstance(batch, list):
            raise AuditError("GitHub release list is not an array")
        releases.extend(batch)
        if len(batch) < 100:
            break
    else:
        raise AuditError("release list exceeded 20 pages; cannot verify uniqueness")
    try:
        return CHECKSUMS["find_release"](
            (json.dumps(item) for item in releases), tag
        )
    except ValueError as error:
        raise AuditError(str(error)) from error


def validate_assets(release):
    assets = release.get("assets")
    expected = set(INSTALLERS) | {"SHA256SUMS"}
    if release.get("draft") is False:
        expected.add("update.json")
    if not isinstance(assets, list) or len(assets) != len(expected):
        raise AuditError(f"expected exactly {len(expected)} release assets")
    by_name = {asset.get("name"): asset for asset in assets if isinstance(asset, dict)}
    if set(by_name) != expected or len(by_name) != len(assets):
        raise AuditError("release has missing, duplicate, or unexpected assets")
    for name, asset in by_name.items():
        if (not isinstance(asset.get("id"), int) or asset["id"] <= 0
                or not isinstance(asset.get("size"), int) or asset["size"] <= 0
                or not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", asset.get("digest") or "")):
            raise AuditError(f"{name} has no valid ID, size, or SHA-256 digest")
    try:
        expected_sums = CHECKSUMS["checksums"](release).encode("ascii")
    except ValueError as error:
        raise AuditError(str(error)) from error
    return by_name, expected_sums


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download_asset(asset, path):
    with path.open("wb") as target:
        result = subprocess.run(
            ["gh", "api", "-H", "Accept: application/octet-stream",
             f"repos/{REPO}/releases/assets/{asset['id']}"],
            stdout=target, stderr=subprocess.PIPE, check=False, timeout=1800,
        )
    if result.returncode:
        raise AuditError(f"download failed for {asset['name']}: "
                         f"{result.stderr.decode(errors='replace').strip()}")
    if path.stat().st_size != asset["size"]:
        raise AuditError(f"{asset['name']} size differs from GitHub metadata")
    digest = sha256(path)
    if digest != asset["digest"][7:].lower():
        raise AuditError(f"{asset['name']} SHA-256 differs from GitHub metadata")
    return digest


def validate_update_manifest(path, release):
    """Check the bytes running copies read against the published release."""
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise AuditError(f"update.json is not valid UTF-8 JSON: {error}") from error
    if not isinstance(manifest, dict):
        raise AuditError("update.json is not an object")
    tag = release.get("tag_name")
    if not isinstance(tag, str) or not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise AuditError("published release has an invalid tag")
    if manifest.get("version") != tag[1:]:
        raise AuditError("update.json version differs from the release tag")
    page = f"https://github.com/{REPO}/releases/tag/{tag}"
    if manifest.get("page") != page:
        raise AuditError("update.json release page differs from the tag page")
    if manifest.get("notes") != (release.get("body") or "")[:4000]:
        raise AuditError("update.json notes differ from the release notes")
    expected = {asset["name"]: {key: asset[key] for key in ("name", "size", "digest")}
                for asset in release["assets"] if asset["name"] in INSTALLERS}
    assets = manifest.get("assets")
    if not isinstance(assets, list) or len(assets) != len(expected):
        raise AuditError("update.json has an incomplete installer list")
    names = [asset.get("name") for asset in assets if isinstance(asset, dict)]
    if (len(names) != len(assets) or not all(isinstance(name, str) for name in names)
            or len(names) != len(set(names))):
        raise AuditError("update.json has invalid or duplicate installer entries")
    if {asset["name"]: asset for asset in assets} != expected:
        raise AuditError("update.json installers differ from the release assets")
    return {"version": manifest["version"], "installers": len(assets)}


def inspect_package(path, name, version):
    if name.endswith(".zip"):
        with zipfile.ZipFile(path) as archive:
            bad = archive.testzip()
            if bad is not None:
                raise AuditError(f"{name} has a bad ZIP member: {bad}")
            detail = {"zipCrc": "ok", "members": len(archive.infolist())}
            if "-mac-" in name:
                matches = [entry for entry in archive.namelist()
                           if entry.endswith("Frame Control.app/Contents/Info.plist")]
                if len(matches) != 1:
                    raise AuditError(f"{name} has {len(matches)} app Info.plist files")
                found = plistlib.loads(archive.read(matches[0])).get("CFBundleShortVersionString")
                if found != version:
                    raise AuditError(f"{name} bundle version {found!r} is not {version}")
                detail["bundleVersion"] = found
            return detail
    if name.endswith(".deb"):
        result = subprocess.run(
            ["dpkg-deb", "-f", str(path), "Version", "Architecture"],
            capture_output=True, text=True, check=False, timeout=60,
        )
        fields = [line.partition(":")[2].strip() for line in result.stdout.splitlines()]
        architecture = "arm64" if "arm64" in name else "amd64"
        if result.returncode or fields != [version, architecture]:
            raise AuditError(f"{name} DEB version/architecture mismatch: {fields}")
        return {"debVersion": fields[0], "architecture": fields[1]}
    if name.endswith(".AppImage"):
        with path.open("rb") as source:
            head = source.read(20)
        machine = struct.unpack("<H", head[18:20])[0] if len(head) >= 20 else None
        expected = 183 if "arm64" in name else 62
        if head[:4] != b"\x7fELF" or machine != expected:
            raise AuditError(f"{name} ELF machine {machine!r} is not {expected}")
        return {"elfMachine": machine}
    if name.endswith(".dmg"):
        if path.stat().st_size < 512:
            raise AuditError(f"{name} is too small for a UDIF trailer")
        with path.open("rb") as source:
            source.seek(-512, 2)
            trailer = source.read(512)
        if trailer[:4] != b"koly":
            raise AuditError(f"{name} has no UDIF trailer")
        return {"udifTrailer": "ok"}
    if name.endswith(".exe"):
        with path.open("rb") as source:
            head = source.read(64)
            if len(head) < 64 or head[:2] != b"MZ":
                raise AuditError(f"{name} has no MZ header")
            source.seek(struct.unpack("<I", head[60:64])[0])
            pe = source.read(6)
        machine = struct.unpack("<H", pe[4:6])[0] if len(pe) == 6 else None
        if pe[:4] != b"PE\x00\x00" or machine not in (0x14C, 0x8664):
            raise AuditError(f"{name} has an invalid PE header or machine")
        return {"peMachine": machine}
    raise AuditError(f"no package inspection for {name}")


def audit(tag, report_path, launch_x86_appimage=False):
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise AuditError("expected a version tag such as v0.4.54")
    if report_path.exists():
        raise AuditError(f"report already exists; choose a new path: {report_path}")
    if not report_path.parent.is_dir():
        raise AuditError(f"report directory does not exist: {report_path.parent}")
    if not shutil.which("gh") or not shutil.which("dpkg-deb"):
        raise AuditError("gh and dpkg-deb are required on the audit host")
    if launch_x86_appimage and not shutil.which("xvfb-run"):
        raise AuditError("xvfb-run is required for --launch-x86-appimage")
    if launch_x86_appimage and platform.machine().lower() not in ("x86_64", "amd64"):
        raise AuditError("--launch-x86-appimage requires an x86_64 audit host")
    release = find_release(tag)
    by_name, expected_sums = validate_assets(release)
    with tempfile.TemporaryDirectory(prefix=f"frame-{tag}-assets-") as directory:
        scratch = Path(directory)
        sums_path = scratch / "SHA256SUMS"
        sums_hash = download_asset(by_name["SHA256SUMS"], sums_path)
        if sums_path.read_bytes() != expected_sums:
            raise AuditError("SHA256SUMS bytes differ from the ten GitHub asset digests")
        manifest_detail = None
        if not release.get("draft"):
            manifest_path = scratch / "update.json"
            manifest_digest = download_asset(by_name["update.json"], manifest_path)
            manifest_detail = validate_update_manifest(manifest_path, release)
            manifest_detail["sha256"] = manifest_digest
        rows = []
        for name in INSTALLERS:
            path = scratch / name
            asset = by_name[name]
            digest = download_asset(asset, path)
            detail = inspect_package(path, name, tag[1:])
            if launch_x86_appimage and name == "Frame-Control-linux-x86_64.AppImage":
                path.chmod(0o755)
                result = subprocess.run(
                    [sys.executable, str(SCRIPTS / "check-appimage-launch.py"), str(path)],
                    capture_output=True, text=True, check=False, timeout=120,
                )
                if result.returncode or digest not in result.stdout:
                    raise AuditError(f"isolated AppImage launch failed: {result.stderr.strip()}")
                detail["appimageLaunch"] = "HTTP 200; FrameControl/1; server stopped"
            rows.append({"name": name, "size": asset["size"], "sha256": digest, **detail})
            path.unlink()
            print(f"verified {name}", flush=True)
    report = {"tag": tag, "releaseId": release["id"],
              "tagNameAtAudit": release.get("tag_name"), "draftAtAudit": release.get("draft"),
              "sha256sumsSha256": sums_hash, "updateManifest": manifest_detail,
              "assets": rows}
    with report_path.open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2)
        output.write("\n")
    print(f"verified {len(rows)} installer downloads; report {report_path}")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tag", help="release tag, for example v0.4.54")
    parser.add_argument("--report", required=True, type=Path, help="new JSON report path")
    parser.add_argument("--launch-x86-appimage", action="store_true",
                        help="also launch the tagged x86_64 AppImage in isolated Xvfb")
    args = parser.parse_args()
    try:
        audit(args.tag, args.report, args.launch_x86_appimage)
    except (AuditError, OSError, subprocess.TimeoutExpired,
            zipfile.BadZipFile, plistlib.InvalidFileException) as error:
        parser.exit(1, f"asset audit failed: {error}\n")


if __name__ == "__main__":
    main()
