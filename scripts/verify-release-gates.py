#!/usr/bin/env python3
"""Refuse publication unless the exact tag commit and tagged installers passed CI.

This checks GitHub's current run and job records, not a prior PR's check marks.
The real Frame smoke and independent package checks remain release-procedure
gates documented in docs/releasing.md.
"""
import json
import subprocess
import sys
from urllib.parse import quote


REPO = "saphid/frame-control"
MAIN_JOBS = {
    "checks", "e2e", "ios", "wireless-windows",
    "server-tests (ubuntu-latest, 3.13)",
    "server-tests (macos-latest, 3.12)",
    "server-tests (windows-latest, 3.12)",
}
RELEASE_JOBS = {
    "draft", "checksums",
    "build (windows-latest, dist:win, app/dist/*.exe app/dist/*.zip)",
    "build (ubuntu-latest, dist:linux, app/dist/*.AppImage app/dist/*.deb)",
    "build (macos-15-intel, dist:mac:x64, app/dist/*.dmg app/dist/*.zip)",
    "build (macos-latest, dist, app/dist/*.dmg app/dist/*.zip)",
}
DECKY_JOBS = {"decky-runtime (ubuntu-latest)", "decky-runtime (ubuntu-24.04-arm)"}


class GateError(Exception):
    pass


def api(path):
    # publish-release.sh already requires sh. Resolve gh through that same
    # shell: on Git Bash, Python's Windows CreateProcess skips an extensionless
    # test gh shim in PATH and accidentally launches the real gh.exe instead.
    command = ["sh", "-c", 'gh api "$1"', "sh", f"repos/{REPO}/{path}"]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode:
        raise GateError(f"GitHub gate read failed for {path}: {result.stderr.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise GateError(f"invalid GitHub gate response for {path}: {error}") from error


def tag_commit(tag):
    target = api(f"git/ref/tags/{quote(tag, safe='')}").get("object") or {}
    for _ in range(5):
        kind, sha = target.get("type"), target.get("sha")
        if not isinstance(sha, str) or len(sha) != 40:
            raise GateError(f"{tag} has no valid tag target")
        if kind == "commit":
            return sha
        if kind != "tag":
            raise GateError(f"{tag} points to unsupported Git object {kind!r}")
        target = api(f"git/tags/{sha}").get("object") or {}
    raise GateError(f"{tag} has too many nested tag objects")


def exact_run(workflow, branch, sha, event):
    query = f"actions/workflows/{workflow}/runs?branch={quote(branch, safe='')}&head_sha={sha}&per_page=100"
    runs = api(query).get("workflow_runs") or []
    matching = [run for run in runs if run.get("head_sha") == sha
                and run.get("head_branch") == branch and run.get("event") == event]
    if not matching:
        raise GateError(f"no exact {workflow} {event} run for {branch} at {sha}")
    run = max(matching, key=lambda item: item["id"])
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise GateError(f"{workflow} run {run['id']} is {run.get('status')}/{run.get('conclusion')}")
    return run


def successful_jobs(run, required):
    attempt = run.get("run_attempt")
    if not isinstance(attempt, int) or attempt < 1:
        raise GateError(f"run {run['id']} has no valid attempt number")
    latest_jobs = None
    for number in range(1, attempt + 1):
        data = api(f"actions/runs/{run['id']}/attempts/{number}/jobs?per_page=100")
        jobs = data.get("jobs") or []
        if data.get("total_count") != len(jobs):
            raise GateError(f"run {run['id']} attempt {number} has more jobs than the gate inspected")
        names = [job.get("name") for job in jobs]
        if not jobs or len(names) != len(set(names)):
            raise GateError(f"run {run['id']} attempt {number} has missing or duplicate jobs")
        bad = [f"{job.get('name')}: {job.get('status')}/{job.get('conclusion')}"
               for job in jobs if job.get("status") != "completed" or job.get("conclusion") != "success"]
        if bad:
            raise GateError(f"run {run['id']} attempt {number} has unfinished, failed, cancelled, or skipped jobs: {bad}")
        latest_jobs = jobs
    names = [job.get("name") for job in latest_jobs]
    if not required.issubset(names):
        missing = sorted(required.difference(names))
        raise GateError(f"run {run['id']} has missing jobs in its latest attempt: {missing}")
    print(f"gate passed: {run.get('html_url')} ({len(latest_jobs)} jobs, {attempt} attempts)")


def main(tag):
    if not tag.startswith("v") or not tag[1:]:
        raise GateError("expected a version tag beginning with v")
    sha = tag_commit(tag)
    successful_jobs(exact_run("checks.yml", "main", sha, "push"), MAIN_JOBS)
    successful_jobs(exact_run("decky-runtime.yml", "main", sha, "push"), DECKY_JOBS)
    successful_jobs(exact_run("release.yml", tag, sha, "push"), RELEASE_JOBS)
    print(f"exact release commit: {sha}")


if __name__ == "__main__":
    try:
        main(sys.argv[1])
    except (IndexError, GateError) as error:
        sys.exit(f"release gate failed: {error}")
