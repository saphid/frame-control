"""Independent release audit rejects incomplete metadata and wrong package versions."""
import sandbox  # noqa: F401  (first: keeps tests off real data and services)
import hashlib
import importlib.util
import json
import plistlib
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit-release-assets.py"
spec = importlib.util.spec_from_file_location("audit_release_assets", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def release_assets():
    assets = []
    for number, name in enumerate(audit.INSTALLERS, 1):
        assets.append({
            "id": number, "name": name, "size": number,
            "digest": "sha256:" + hashlib.sha256(str(number).encode()).hexdigest(),
        })
    sums = audit.CHECKSUMS["checksums"]({"assets": assets}).encode("ascii")
    assets.append({
        "id": 99, "name": "SHA256SUMS", "size": len(sums),
        "digest": "sha256:" + hashlib.sha256(sums).hexdigest(),
    })
    return assets, sums


class AssetAudit(unittest.TestCase):
    def test_release_lookup_rejects_matching_draft_on_later_page(self):
        first = {"id": 42, "tag_name": "untagged-first", "draft": True,
                 "name": "Frame Control 9.8.7"}
        second = {"id": 43, "tag_name": "untagged-second", "draft": True,
                  "name": "Frame Control 9.8.7"}
        first_page = [first] + [
            {"id": number, "tag_name": f"v0.0.{number}", "draft": False}
            for number in range(1, 100)
        ]
        with mock.patch.object(audit, "github_json", side_effect=[first_page, [second]]) as github:
            with self.assertRaisesRegex(audit.AuditError, "expected one release"):
                audit.find_release("v9.8.7")
        self.assertEqual(github.call_count, 2)

    def test_release_lookup_finds_match_after_full_first_page(self):
        first_page = [
            {"id": number, "tag_name": f"v0.0.{number}", "draft": False}
            for number in range(1, 101)
        ]
        matching = {"id": 42, "tag_name": "v9.8.7", "draft": True}
        with mock.patch.object(audit, "github_json", side_effect=[first_page, [matching]]) as github:
            self.assertEqual(audit.find_release("v9.8.7"), matching)
        self.assertEqual(github.call_count, 2)

    def test_release_lookup_refuses_unfinished_pagination(self):
        page = [{"id": number, "tag_name": "v9.8.7" if number == 1 else f"v0.0.{number}"}
                for number in range(1, 101)]
        with mock.patch.object(audit, "github_json", return_value=page) as github:
            with self.assertRaisesRegex(audit.AuditError, "cannot verify uniqueness"):
                audit.find_release("v9.8.7")
        self.assertEqual(github.call_count, 20)

    def test_published_manifest_matches_release_bytes(self):
        assets, _ = release_assets()
        release = {"tag_name": "v9.8.7", "body": "Release notes", "assets": assets}
        manifest = {
            "version": "9.8.7",
            "page": "https://github.com/saphid/frame-control/releases/tag/v9.8.7",
            "notes": "Release notes",
            "assets": [{key: asset[key] for key in ("name", "size", "digest")}
                       for asset in assets if asset["name"] in audit.INSTALLERS],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "update.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual(audit.validate_update_manifest(path, release),
                             {"version": "9.8.7", "installers": 10})
            for change in (
                {"version": "9.8.6"},
                {"page": "https://github.com/elsewhere/releases/tag/v9.8.7"},
                {"notes": "stale notes"},
                {"assets": manifest["assets"][:-1]},
                {"assets": [dict(manifest["assets"][0], digest="sha256:" + "0" * 64),
                            *manifest["assets"][1:]]},
            ):
                with self.subTest(change=change):
                    path.write_text(json.dumps({**manifest, **change}), encoding="utf-8")
                    with self.assertRaises(audit.AuditError):
                        audit.validate_update_manifest(path, release)

    def test_complete_metadata_uses_release_checksum_order(self):
        assets, sums = release_assets()
        by_name, expected = audit.validate_assets({"assets": assets})
        self.assertEqual(len(by_name), 11)
        self.assertEqual(expected, sums)

    def test_published_release_requires_update_manifest(self):
        assets, sums = release_assets()
        manifest = {"id": 100, "name": "update.json", "size": 20,
                    "digest": "sha256:" + "a" * 64}
        with self.assertRaises(audit.AuditError):
            audit.validate_assets({"draft": False, "assets": assets})
        by_name, expected = audit.validate_assets({"draft": False, "assets": [*assets, manifest]})
        self.assertEqual(len(by_name), 12)
        self.assertEqual(expected, sums)

    def test_missing_duplicate_and_unhashed_assets_fail(self):
        assets, _ = release_assets()
        variants = (
            assets[:-1],
            [*assets, assets[0]],
            [dict(assets[0], digest="sha256:bad"), *assets[1:]],
            [dict(assets[0], size=0), *assets[1:]],
        )
        for changed in variants:
            with self.subTest(changed=changed[0]), self.assertRaises(audit.AuditError):
                audit.validate_assets({"assets": changed})

    def test_mac_zip_bundle_version_must_match_tag(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mac.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(
                    "Frame Control.app/Contents/Info.plist",
                    plistlib.dumps({"CFBundleShortVersionString": "9.8.7"}),
                )
            self.assertEqual(
                audit.inspect_package(path, "Frame-Control-mac-arm64.zip", "9.8.7")["bundleVersion"],
                "9.8.7",
            )
            with self.assertRaises(audit.AuditError):
                audit.inspect_package(path, "Frame-Control-mac-arm64.zip", "9.8.8")

    def test_appimage_machine_must_match_name(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image"
            path.write_bytes(b"\x7fELF" + bytes(14) + struct.pack("<H", 183))
            self.assertEqual(
                audit.inspect_package(path, "Frame-Control-linux-arm64.AppImage", "9.8.7"),
                {"elfMachine": 183},
            )
            with self.assertRaises(audit.AuditError):
                audit.inspect_package(path, "Frame-Control-linux-x86_64.AppImage", "9.8.7")

    def test_existing_report_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_text("keep")
            with self.assertRaisesRegex(audit.AuditError, "already exists"):
                audit.audit("v9.8.7", path)
            self.assertEqual(path.read_text(), "keep")

    def test_missing_report_directory_fails_before_download(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing" / "report.json"
            with self.assertRaisesRegex(audit.AuditError, "directory does not exist"):
                audit.audit("v9.8.7", path)

    def test_bad_downloaded_checksum_file_creates_no_report(self):
        assets, _ = release_assets()
        release = {"id": 42, "tag_name": "v9.8.7", "draft": True, "assets": assets}

        def bad_download(asset, path):
            path.write_bytes(b"wrong checksum file\n")
            return asset["digest"][7:]

        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            with mock.patch.object(audit, "find_release", return_value=release), \
                 mock.patch.object(audit, "download_asset", side_effect=bad_download), \
                 mock.patch.object(audit.shutil, "which", return_value="/fake/tool"):
                with self.assertRaisesRegex(audit.AuditError, "SHA256SUMS bytes differ"):
                    audit.audit("v9.8.7", report)
            self.assertFalse(report.exists())

    def test_bad_published_manifest_creates_no_report(self):
        assets, sums = release_assets()
        assets.append({"id": 100, "name": "update.json", "size": 2,
                       "digest": "sha256:" + hashlib.sha256(b"{}").hexdigest()})
        release = {"id": 42, "tag_name": "v9.8.7", "draft": False,
                   "body": "Release notes", "assets": assets}

        def download(asset, path):
            path.write_bytes(sums if asset["name"] == "SHA256SUMS" else b"{}")
            return asset["digest"][7:]

        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            with mock.patch.object(audit, "find_release", return_value=release), \
                 mock.patch.object(audit, "download_asset", side_effect=download), \
                 mock.patch.object(audit.shutil, "which", return_value="/fake/tool"):
                with self.assertRaisesRegex(audit.AuditError, "version differs"):
                    audit.audit("v9.8.7", report)
            self.assertFalse(report.exists())


if __name__ == "__main__":
    unittest.main()
