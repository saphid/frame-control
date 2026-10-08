"""The "Create the draft release" step of .github/workflows/release.yml, taken out of
the workflow and run with bash (as Actions runs it) against a stand-in gh
(tests/fakegh/gh): a new draft's id comes straight from the POST even when the
release list doesn't show it yet (v0.4.2's first run), a rerun reuses the draft
found by tag_name, and a tag that isn't on GitHub stops it. Nothing here talks to
GitHub.

Run: python3 -m unittest discover -s tests
"""
import sandbox  # noqa: F401  (first: keeps tests off real data and services)
import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
FAKEGH = ROOT / "tests" / "fakegh"
STEP = "- name: Create the draft release"


def step_script():
    """The step's `run: |` block, dedented."""
    lines = WORKFLOW.read_text().splitlines()
    i = next(n for n, line in enumerate(lines) if line.strip() == STEP)
    while lines[i].strip() != "run: |":
        i += 1
    indent = len(lines[i]) - len(lines[i].lstrip())
    body = []
    for line in lines[i + 1:]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        body.append(line)
    return textwrap.dedent("\n".join(body)).strip() + "\n"


def release(rid, tag_name, name="Frame Control 9.8.7", draft=True):
    return {"id": rid, "tag_name": tag_name, "name": name, "draft": draft, "assets": []}


@unittest.skipUnless(shutil.which("bash") and shutil.which("jq"), "needs bash and jq (for gh --jq)")
class DraftStep(unittest.TestCase):
    def run_step(self, releases, tags="v9.8.7", tag="v9.8.7"):
        d = Path(tempfile.mkdtemp())
        (d / "step.sh").write_text(step_script())
        (d / "releases.json").write_text(json.dumps(releases))
        env = dict(os.environ, PATH="%s:%s" % (FAKEGH, os.environ["PATH"]),
                   FAKEGH_RELEASES=str(d / "releases.json"), FAKEGH_TAGS=tags,
                   FAKEGH_LOG=str(d / "log"), GITHUB_REF_NAME=tag, GH_REPO="saphid/frame-control")
        p = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", str(d / "step.sh")],
                           env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           universal_newlines=True, timeout=30)
        log = [json.loads(line) for line in (d / "log").read_text().splitlines()] if (d / "log").exists() else []
        return p, log

    def posts(self, log):
        return [c for c in log if c[1:4] == ["-X", "POST", "repos/saphid/frame-control/releases"]]

    def patches(self, log):
        return [c for c in log if c[1:3] == ["-X", "PATCH"]]

    def test_new_draft_uses_the_id_the_post_returns(self):
        # The list doesn't show the fresh draft (it never does in the fake): v0.4.2's case.
        p, log = self.run_step([])
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        [post] = self.posts(log)
        for f in ("tag_name=v9.8.7", "name=Frame Control 9.8.7", "draft=true"):
            self.assertIn(f, post)
        self.assertIn(["api", "repos/saphid/frame-control/git/ref/tags/v9.8.7"], log)
        [patch] = self.patches(log)
        self.assertEqual(patch[3], "repos/saphid/frame-control/releases/9001")
        self.assertIn("tag_name=v9.8.7", patch)
        self.assertIn("release 9001 tag_name v9.8.7", p.stdout)
        self.assertTrue(all(c[0] == "api" for c in log))  # never `gh release ...`

    def test_a_rerun_reuses_the_draft_with_the_tag(self):
        p, log = self.run_step([release(7, "v9.8.6", "Frame Control 9.8.6"), release(42, "v9.8.7")])
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        self.assertEqual(self.posts(log), [])
        [patch] = self.patches(log)
        self.assertEqual(patch[3], "repos/saphid/frame-control/releases/42")

    def test_other_releases_alone_mean_a_new_draft(self):
        p, log = self.run_step([release(7, "v9.8.6", "Frame Control 9.8.6", draft=False),
                                release(8, "v9.8.70", "Frame Control 9.8.70")])
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        self.assertEqual(len(self.posts(log)), 1)
        self.assertEqual(self.patches(log)[0][3], "repos/saphid/frame-control/releases/9001")

    def test_stops_when_the_tag_is_not_on_github(self):
        p, log = self.run_step([], tags="")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("tag v9.8.7 isn't on GitHub", p.stderr)
        self.assertEqual(self.posts(log), [])
        self.assertEqual(self.patches(log), [])


if __name__ == "__main__":
    unittest.main()
