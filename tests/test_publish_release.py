"""scripts/publish-release.sh against a stand-in gh (tests/fakegh/gh): finds the draft
through the REST API even when its tag_name still says untagged-..., refuses
missing installers or digests, writes update.json's page from the tag, and
publishes with one PATCH. Nothing here talks to GitHub.

Run: python3 -m unittest discover -s tests
"""
import sandbox  # noqa: F401  (first: keeps tests off real data and services)
import json
import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAKEGH = ROOT / "tests" / "fakegh"
INSTALLERS = ["Frame-Control-mac-arm64.dmg", "Frame-Control-mac-arm64.zip",
              "Frame-Control-mac-x64.dmg", "Frame-Control-mac-x64.zip", "Frame-Control-Setup-x64.exe",
              "Frame-Control-win-x64.zip", "Frame-Control-linux-x86_64.AppImage",
              "Frame-Control-linux-arm64.AppImage", "Frame-Control-linux-amd64.deb",
              "Frame-Control-linux-arm64.deb"]


def draft(tag_name="untagged-c6ddfed7f75d67db2e99", name="Frame Control 9.8.7", rid=42, assets=None):
    if assets is None:
        assets = [{"id": 100 + i, "name": n, "size": 1000 + i, "digest": "sha256:" + "%064x" % i}
                  for i, n in enumerate(INSTALLERS)]
        body = "".join(f"{i:064x}  {n}\n" for i, n in enumerate(INSTALLERS)).encode()
        assets.append({"id": 200, "name": "SHA256SUMS", "size": len(body),
                       "digest": "sha256:" + hashlib.sha256(body).hexdigest()})
    return {"id": rid, "tag_name": tag_name, "name": name, "draft": True, "prerelease": False,
            "body": "notes", "html_url": "https://github.com/saphid/frame-control/releases/tag/" + tag_name,
            "assets": assets}


def asset_audit(release, tag="v9.8.7"):
    rows = []
    for asset in release['assets']:
        name = asset['name']
        if name not in INSTALLERS:
            continue
        row = {'name': name, 'size': asset['size'], 'sha256': asset['digest'][7:] if asset['digest'] else ''}
        if name.endswith('.dmg'):
            row['udifTrailer'] = 'ok'
        elif name.endswith('.zip'):
            row.update(zipCrc='ok', members=1)
            if '-mac-' in name:
                row['bundleVersion'] = tag[1:]
        elif name.endswith('.exe'):
            row['peMachine'] = 0x8664
        elif name.endswith('.AppImage'):
            row['elfMachine'] = 183 if 'arm64' in name else 62
            if 'x86_64' in name:
                row['appimageLaunch'] = 'HTTP 200; FrameControl/1; server stopped'
        elif name.endswith('.deb'):
            row.update(debVersion=tag[1:], architecture='arm64' if 'arm64' in name else 'amd64')
        rows.append(row)
    sums = next((asset['digest'] for asset in release['assets'] if asset['name'] == 'SHA256SUMS'), '')
    return {'tag': tag, 'releaseId': release['id'], 'tagNameAtAudit': release['tag_name'],
            'draftAtAudit': True, 'sha256sumsSha256': sums[7:], 'updateManifest': None,
            'assets': rows}


class PublishRelease(unittest.TestCase):
    def run_script(self, releases, *args, tags="v9.8.7", gates=None,
                   corrupt_manifest_readback=False, smoke=None, audit=None,
                   local_head=None, local_dirty=False, local_status_fail=False,
                   local_version="9.8.7"):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        checkout = d / "checkout"
        scripts = checkout / "scripts"
        scripts.mkdir(parents=True)
        for name in ("publish-release.sh", "verify-release-gates.py",
                     "verify-frame-smoke-result.py", "release-checksums.py",
                     "verify-release-asset-audit.py", "release-safety-note.md"):
            shutil.copy2(ROOT / "scripts" / name, scripts / name)
        app = checkout / "app"
        app.mkdir()
        (app / "package.json").write_text(json.dumps({"version": local_version}))
        subprocess.run(["git", "-C", str(checkout), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(checkout), "add", "."], check=True)
        subprocess.run(["git", "-C", str(checkout), "-c", "user.name=Release Test",
                        "-c", "user.email=release-test@example.invalid", "commit", "-qm", "fixture"], check=True)
        commit = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
        tag_commit = local_head or commit
        if local_dirty:
            (checkout / "owned-test-file").write_text("dirty")
        if local_status_fail:
            (checkout / ".git" / "index").write_bytes(b"invalid index")
        (d / "releases.json").write_text(json.dumps(releases))
        (d / "gates.json").write_text(json.dumps({"tag_commit": tag_commit, **(gates or {})}))
        steps = ["cleanup: leftovers from earlier runs", "devkit service: properties.json",
                 "status", "cleanup: everything this run installed"] + [
                     f"{kind}: {action}" for kind in ("arm64", "x86_64", "exe")
                     for action in ("install", "launch", "remove")]
        clean_smoke = {"source": {"commit": tag_commit, "clean": True},
                       "simulated": False, "lock_released": True,
                       "steps": [{"step": name, "ok": True} for name in steps],
                       "passed": len(steps), "skipped": 0, "failed": 0,
                       "preflight": {"activity": 3, "proximity": [2.3125], "battery": [100]}}
        if smoke == "skipped":
            clean_smoke["steps"][0].update(ok=False, skipped=True)
            clean_smoke.update(passed=len(steps) - 1, skipped=1)
        elif smoke == "unreleased":
            clean_smoke["lock_released"] = False
        if smoke is not False:
            (d / "smoke.json").write_text(json.dumps(
                clean_smoke if smoke is None or isinstance(smoke, str) else smoke))
        matching = next((r for r in releases if r.get('tag_name') == tags), None)
        matching = matching or next((r for r in releases if r.get('name', '').startswith('Frame Control 9.8.7')), None)
        if audit is not False and matching:
            (d / 'asset-audit.json').write_text(json.dumps(
                asset_audit(matching, tags) if audit is None else audit))
        env = dict(os.environ, PATH="%s:%s" % (FAKEGH, os.environ["PATH"]),
                   FAKEGH_RELEASES=str(d / "releases.json"), FAKEGH_TAGS=tags,
                   FAKEGH_LOG=str(d / "log"), FAKEGH_UPLOAD=str(d / "upload.json"),
                   FAKEGH_GATES=str(d / "gates.json"),
                   FAKEGH_CORRUPT_MANIFEST_READBACK="1" if corrupt_manifest_readback else "0")
        env.pop("FRAME_SMOKE_RESULT", None)
        if smoke is not False:
            env["FRAME_SMOKE_RESULT"] = str(d / "smoke.json")
        if audit is not False:
            env['RELEASE_ASSET_AUDIT'] = str(d / 'asset-audit.json')
        else:
            env.pop('RELEASE_ASSET_AUDIT', None)
        p = subprocess.run(["sh", str(scripts / "publish-release.sh"), *args],
                           env=env, capture_output=True, text=True, timeout=30)
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
        readback = next(c for c in log if any("releases/assets/901" in arg for arg in c))
        self.assertLess(log.index(readback), log.index(patch))
        self.assertEqual(patch[3], "repos/saphid/frame-control/releases/42")
        for f in ("tag_name=v9.8.7", "draft=false", "prerelease=false", "make_latest=true"):
            self.assertIn(f, patch)
        self.assertTrue(all(c[0] == "api" for c in log))  # never `gh release ...` (GraphQL)

    def test_refuses_mismatched_manifest_readback_before_publication(self):
        p, log, upload = self.run_script([draft()], "v9.8.7",
                                         corrupt_manifest_readback=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("downloaded update.json differs", p.stderr)
        self.assertIsNotNone(upload)
        self.assertFalse(any("PATCH" in call for call in log))

    def test_an_untagged_draft_may_carry_a_subtitle(self):
        p, log, upload = self.run_script([draft(name="Frame Control 9.8.7: faster")], "v9.8.7")
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        self.assertEqual(upload["version"], "9.8.7")

    def test_prefers_the_release_whose_tag_name_matches(self):
        p, log, upload = self.run_script([draft(name="Frame Control 9.8.7 old", rid=1),
                                          draft(tag_name="v9.8.7", name="Renamed", rid=2)], "v9.8.7")
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        self.assertEqual(next(c for c in log if "PATCH" in c)[3], "repos/saphid/frame-control/releases/2")

    def test_already_published_release_keeps_its_live_update_manifest(self):
        old = {"id": 7, "name": "update.json", "size": 100,
               "digest": "sha256:" + "a" * 64}
        rel = dict(draft(tag_name="v9.8.7", assets=draft()["assets"] + [old]), draft=False)
        p, log, upload = self.run_script([rel], "v9.8.7")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("already published", p.stderr)
        self.assertIsNone(upload)
        self.assertFalse(any("-X" in call for call in log))

    def test_refuses_missing_or_unhashed_installers(self):
        assets = draft()["assets"][1:]
        assets[0] = dict(assets[0], digest=None)
        p, log, upload = self.run_script([draft(assets=assets)], "v9.8.7")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("MISSING  Frame-Control-mac-arm64.dmg", p.stdout)
        self.assertIn("NO HASH  Frame-Control-mac-arm64.zip", p.stdout)
        self.assertIsNone(upload)
        self.assertFalse(any(c[1:3] == ["-X", "PATCH"] for c in log))

    def test_refuses_missing_or_stale_checksums(self):
        for assets in (draft()["assets"][:-1],
                       draft()["assets"][:-1] + [{"id": 200, "name": "SHA256SUMS",
                                                  "digest": "sha256:" + "0" * 64}]):
            p, log, upload = self.run_script([draft(assets=assets)], "v9.8.7")
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("SHA256SUMS is absent or does not match", p.stderr)
            self.assertIsNone(upload)
            self.assertFalse(any("PATCH" in c for c in log))

    def test_refuses_ambiguous_or_absent_drafts_and_missing_tags(self):
        p, _, _ = self.run_script([draft(rid=1), draft(rid=2)], "v9.8.7")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("2 releases", p.stderr)
        p, _, _ = self.run_script([draft(name="Frame Control 9.8.70")], "v9.8.7")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("no release", p.stderr)
        # A pre-release's draft, or one bound to an unrelated tag, is never taken for v9.8.7.
        for rel in (draft(name="Frame Control 9.8.7-rc.1"), draft(name="Frame Control 9.8.7.1"),
                    draft(tag_name="kdeconnect-frame-1"), draft(tag_name="")):
            p, log, upload = self.run_script([rel], "v9.8.7")
            self.assertNotEqual(p.returncode, 0, rel)
            self.assertIn("no release", p.stderr)
            self.assertIsNone(upload)
            self.assertFalse(any("PATCH" in c for c in log))
        p, log, _ = self.run_script([draft()], "v9.8.7", tags="")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("push it first", p.stderr)

    def test_dry_run_changes_nothing(self):
        p, log, upload = self.run_script([draft()], "--dry-run", "v9.8.7")
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        self.assertIn('"page": "https://github.com/saphid/frame-control/releases/tag/v9.8.7"', p.stdout)
        self.assertIsNone(upload)
        self.assertTrue(all("-X" not in c for c in log))

    def test_refuses_wrong_dirty_or_misversioned_local_checkout(self):
        for kwargs, message in (({'local_head': 'b' * 40}, 'differs from release commit'),
                                ({'local_dirty': True}, 'uncommitted or untracked'),
                                ({'local_status_fail': True}, 'could not inspect local release checkout'),
                                ({'local_version': '9.8.8'}, 'package version')):
            with self.subTest(kwargs=kwargs):
                p, log, upload = self.run_script([draft()], 'v9.8.7', **kwargs)
                self.assertNotEqual(p.returncode, 0)
                self.assertIn(message, p.stderr)
                self.assertIsNone(upload)
                self.assertFalse(any('-X' in call for call in log))

    def test_refuses_failed_e2e_or_cancelled_installer_before_mutation(self):
        for gates in ({"bad_job": "e2e", "bad_job_conclusion": "failure"},
                      {"bad_job": "decky-runtime (ubuntu-24.04-arm)",
                       "bad_job_conclusion": "failure"},
                      {"bad_job": "build (macos-latest, dist, app/dist/*.dmg app/dist/*.zip)",
                       "bad_job_conclusion": "cancelled"}):
            p, log, upload = self.run_script([draft()], "v9.8.7", gates=gates)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("release gate failed", p.stderr)
            self.assertIsNone(upload)
            self.assertFalse(any("-X" in call for call in log))

    def test_refuses_missing_or_skipped_frame_smoke_before_mutation(self):
        for smoke in (False,
                      {"source": {"commit": "b" * 40, "clean": True}},
                      {"source": {"commit": "a" * 40, "clean": False}},
                      "skipped", "unreleased"):
            with self.subTest(smoke=smoke):
                p, log, upload = self.run_script([draft()], "v9.8.7", smoke=smoke)
                self.assertNotEqual(p.returncode, 0)
                self.assertIn("release gate failed", p.stderr)
                self.assertIsNone(upload)
                self.assertFalse(any("-X" in call for call in log))

    def test_prior_main_or_native_run_cannot_be_hidden_by_later_success(self):
        for kind, job in (('main', 'e2e'), ('decky', 'decky-runtime (ubuntu-24.04-arm)')):
            cases = [{f'prior_{kind}_conclusion': state}
                     for state in ('failure', 'cancelled', 'skipped')]
            cases += [{f'prior_{kind}_status': 'in_progress', f'prior_{kind}_conclusion': None},
                      {'prior_runtime_bad_job': job, 'prior_runtime_bad_conclusion': 'failure'}]
            for case in cases:
                gates = {f'prior_{kind}_run': True, **case}
                with self.subTest(gates=gates):
                    p, log, upload = self.run_script([draft()], 'v9.8.7', gates=gates)
                    self.assertNotEqual(p.returncode, 0, p.stdout)
                    self.assertIn('release gate failed', p.stderr)
                    self.assertIsNone(upload)
                    self.assertFalse(any('-X' in call for call in log))

    def test_all_successful_main_and_native_runs_are_checked(self):
        p, log, upload = self.run_script([draft()], '--dry-run', 'v9.8.7',
                                        gates={'prior_main_run': True, 'prior_decky_run': True})
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        for run in (497, 498, 501, 503):
            self.assertTrue(any(f'actions/runs/{run}/attempts/1/jobs' in arg
                                for call in log for arg in call), run)
        self.assertIsNone(upload)
        self.assertFalse(any('-X' in call for call in log))

    def test_signed_package_gates_stop_publication_before_any_mutation(self):
        cases = [{"signed_missing": True}, {"signed_sha": "c" * 40},
                 {"signed_branch": "unrelated"}, {"signed_event": "pull_request"},
                 {"signed_status": "in_progress"}, {"signed_conclusion": "failure"}]
        cases += [{"omit_job": name} for name in (
            "signed-package (ubuntu-latest)", "signed-package (ubuntu-24.04-arm)",
            "signed-package (ubuntu-latest, browser HTTP)",
            "signed-package (ubuntu-latest, production parent HTTP)")]
        cases += [{"bad_job": "signed-package (ubuntu-24.04-arm)",
                   "bad_job_conclusion": conclusion}
                  for conclusion in ("failure", "cancelled", "skipped")]
        cases += [{"prior_signed_run_conclusion": "failure"},
                  {"signed_attempts": 2, "signed_prior_bad_job": "signed-package (ubuntu-latest)",
                   "signed_prior_bad_conclusion": "cancelled"}]
        for gates in cases:
            with self.subTest(gates=gates):
                p, log, upload = self.run_script([draft()], "v9.8.7", gates=gates)
                self.assertNotEqual(p.returncode, 0, p.stdout)
                self.assertIn("release gate failed", p.stderr)
                self.assertRegex(p.stderr, 'syncthing-flatpak-package|signed-package')
                self.assertIsNone(upload)
                self.assertFalse(any("-X" in call for call in log))

    def test_signed_package_push_and_manual_runs_are_accepted(self):
        for event in ("push", "workflow_dispatch"):
            with self.subTest(event=event):
                p, log, upload = self.run_script([draft()], "--dry-run", "v9.8.7",
                                                 gates={"signed_event": event})
                self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
                self.assertTrue(any("syncthing-flatpak-package.yml/runs" in arg
                                    for call in log for arg in call))
                self.assertIsNone(upload)
                self.assertFalse(any("-X" in call for call in log))

    def test_refuses_missing_or_stale_independent_asset_audit(self):
        good = asset_audit(draft())
        cases = [False,
                 dict(good, releaseId=999),
                 dict(good, sha256sumsSha256='0' * 64),
                 dict(good, assets=good['assets'][:-1])]
        changed = json.loads(json.dumps(good))
        changed['assets'][0]['sha256'] = 'f' * 64
        cases.append(changed)
        changed = json.loads(json.dumps(good))
        next(row for row in changed['assets'] if row['name'].endswith('x86_64.AppImage')).pop('appimageLaunch')
        cases.append(changed)
        for audit in cases:
            with self.subTest(audit=audit):
                p, log, upload = self.run_script([draft()], 'v9.8.7', audit=audit)
                self.assertNotEqual(p.returncode, 0)
                self.assertIsNone(upload)
                self.assertFalse(any('-X' in call for call in log))

    def test_refuses_unexpected_draft_asset_outside_the_audit(self):
        extra = {'id': 300, 'name': 'unreviewed-installer.exe', 'size': 123,
                 'digest': 'sha256:' + 'f' * 64}
        p, log, upload = self.run_script([draft(assets=draft()['assets'] + [extra])], 'v9.8.7')
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('outside the audited installer set', p.stderr)
        self.assertIsNone(upload)
        self.assertFalse(any('-X' in call for call in log))

    def test_refuses_a_prior_cancelled_installer_after_successful_rerun(self):
        gates = {"release_attempts": 2,
                 "prior_bad_job": "build (macos-latest, dist, app/dist/*.dmg app/dist/*.zip)",
                 "prior_bad_job_conclusion": "cancelled"}
        p, log, upload = self.run_script([draft()], "v9.8.7", gates=gates)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("attempt 1", p.stderr)
        self.assertIn("cancelled", p.stderr)
        self.assertIsNone(upload)
        self.assertFalse(any("-X" in call for call in log))

    def test_refuses_bad_installer_in_separate_prior_tag_run(self):
        for run_conclusion, job_conclusion, expected in (
                ("failure", "cancelled", "failure"),
                ("success", "skipped", "skipped")):
            with self.subTest(run_conclusion=run_conclusion, job_conclusion=job_conclusion):
                gates = {"prior_release_run_bad_job":
                         "build (macos-latest, dist, app/dist/*.dmg app/dist/*.zip)",
                         "prior_release_run_conclusion": run_conclusion,
                         "prior_release_run_bad_conclusion": job_conclusion}
                p, log, upload = self.run_script([draft()], "v9.8.7", gates=gates)
                self.assertNotEqual(p.returncode, 0)
                self.assertIn("run 500", p.stderr)
                self.assertIn(expected, p.stderr)
                self.assertIsNone(upload)
                self.assertFalse(any("-X" in call for call in log))

    def test_refuses_incomplete_tag_run_list(self):
        p, log, upload = self.run_script([draft()], "v9.8.7",
                                         gates={"release_run_list_incomplete": True})
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("incomplete", p.stderr)
        self.assertIsNone(upload)
        self.assertFalse(any("-X" in call for call in log))

    def test_refuses_missing_or_nonexact_gate_results(self):
        for gates in ({"omit_job": "e2e"}, {"main_sha": "c" * 40},
                      {"decky_conclusion": "failure"}, {"release_conclusion": "failure"},
                      {"release_status": "in_progress"}):
            p, log, upload = self.run_script([draft()], "v9.8.7", gates=gates)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("release gate failed", p.stderr)
            self.assertIsNone(upload)
            self.assertFalse(any("-X" in call for call in log))

    def test_refuses_a_withdrawn_release_even_when_ci_is_green(self):
        rel = dict(draft(), body="> **WITHDRAWN 26 October 2026.** Do not install.\n\n# Notes")
        p, log, upload = self.run_script([rel], "v9.8.7")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("marked WITHDRAWN", p.stderr)
        self.assertIsNone(upload)
        self.assertFalse(any("-X" in call for call in log))


if __name__ == "__main__":
    unittest.main()
