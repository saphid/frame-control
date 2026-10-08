"""scripts/publish-release.sh against a stand-in gh (tests/fakegh/gh): finds the draft
through the REST API even when its tag_name still says untagged-..., refuses
missing installers or digests, writes update.json's page from the tag, and
publishes with one PATCH. Nothing here talks to GitHub.

Run: python3 -m unittest discover -s tests
"""
import sandbox  # noqa: F401  (first: keeps tests off real data and services)
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "publish-release.sh"
FAKEGH = ROOT / "tests" / "fakegh"
INSTALLERS = ["Frame-Control-mac-arm64.dmg", "Frame-Control-mac-arm64.zip", "Frame-Control-Setup-x64.exe",
              "Frame-Control-win-x64.zip", "Frame-Control-linux-x86_64.AppImage",
              "Frame-Control-linux-arm64.AppImage", "Frame-Control-linux-amd64.deb",
              "Frame-Control-linux-arm64.deb"]


def draft(tag_name="untagged-c6ddfed7f75d67db2e99", name="Frame Control 9.8.7", rid=42, assets=None):
    if assets is None:
        assets = [{"id": 100 + i, "name": n, "size": 1000 + i, "digest": "sha256:" + "%064x" % i}
                  for i, n in enumerate(INSTALLERS)]
    return {"id": rid, "tag_name": tag_name, "name": name, "draft": True, "prerelease": False,
            "body": "notes", "html_url": "https://github.com/saphid/frame-control/releases/tag/" + tag_name,
            "assets": assets}


class PublishRelease(unittest.TestCase):
    def run_script(self, releases, *args, tags="v9.8.7"):
        d = Path(tempfile.mkdtemp())
        (d / "releases.json").write_text(json.dumps(releases))
        env = dict(os.environ, PATH="%s:%s" % (FAKEGH, os.environ["PATH"]),
                   FAKEGH_RELEASES=str(d / "releases.json"), FAKEGH_TAGS=tags,
                   FAKEGH_LOG=str(d / "log"), FAKEGH_UPLOAD=str(d / "upload.json"))
        p = subprocess.run(["sh", str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=30)
        log = [json.loads(line) for line in (d / "log").read_text().splitlines()] if (d / "log").exists() else []
        upload = json.loads((d / "upload.json").read_text()) if (d / "upload.json").exists() else None
        return p, log, upload

    def test_publishes_an_untagged_draft_by_title_with_the_tag_page(self):
        old = {"id": 7, "name": "update.json", "size": 1, "digest": None}
        rel = draft(assets=draft()["assets"] + [old])
        p, log, upload = self.run_script([rel], "v9.8.7")
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        self.assertEqual(upload["page"], "https://github.com/saphid/frame-control/releases/tag/v9.8.7")
        self.assertEqual(upload["version"], "9.8.7")
        self.assertEqual(sorted(a["name"] for a in upload["assets"]), sorted(INSTALLERS))
        self.assertIn(["api", "-X", "DELETE", "repos/saphid/frame-control/releases/assets/7"], log)
        patch = next(c for c in log if "PATCH" in c)
        self.assertEqual(patch[3], "repos/saphid/frame-control/releases/42")
        for f in ("tag_name=v9.8.7", "draft=false", "prerelease=false", "make_latest=true"):
            self.assertIn(f, patch)
        self.assertTrue(all(c[0] == "api" for c in log))  # never `gh release ...` (GraphQL)

    def test_prefers_the_release_whose_tag_name_matches(self):
        p, log, upload = self.run_script([draft(name="Frame Control 9.8.7 old", rid=1),
                                          draft(tag_name="v9.8.7", name="Renamed", rid=2)], "v9.8.7")
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        self.assertEqual(next(c for c in log if "PATCH" in c)[3], "repos/saphid/frame-control/releases/2")

    def test_refuses_missing_or_unhashed_installers(self):
        assets = draft()["assets"][1:]
        assets[0] = dict(assets[0], digest=None)
        p, log, upload = self.run_script([draft(assets=assets)], "v9.8.7")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("MISSING  Frame-Control-mac-arm64.dmg", p.stdout)
        self.assertIn("NO HASH  Frame-Control-mac-arm64.zip", p.stdout)
        self.assertIsNone(upload)
        self.assertFalse(any(c[1:3] == ["-X", "PATCH"] for c in log))

    def test_refuses_ambiguous_or_absent_drafts_and_missing_tags(self):
        p, _, _ = self.run_script([draft(rid=1), draft(rid=2)], "v9.8.7")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("2 releases", p.stderr)
        p, _, _ = self.run_script([draft(name="Frame Control 9.8.70")], "v9.8.7")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("no release", p.stderr)
        p, log, _ = self.run_script([draft()], "v9.8.7", tags="")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("push it first", p.stderr)

    def test_dry_run_changes_nothing(self):
        p, log, upload = self.run_script([draft()], "--dry-run", "v9.8.7")
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        self.assertIn('"page": "https://github.com/saphid/frame-control/releases/tag/v9.8.7"', p.stdout)
        self.assertIsNone(upload)
        self.assertTrue(all("-X" not in c for c in log))


if __name__ == "__main__":
    unittest.main()
