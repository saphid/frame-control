"""Guest-only signed package and private service/sync checks; no Decky shim."""

import configparser
import hashlib
import json
import os
import shutil
import signal
import subprocess
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
import gi

gi.require_version("OSTree", "1.0")
from gi.repository import Gio, OSTree, GLib

APP = "me.kozec.syncthingtk"
PROGRESS = {}
ARCH = os.uname().machine
EXPECTED = {
    "x86_64": {
        "app": "2be395a769ce7f1d8332892c1777d9f1f147ce7f66647864d87d5550e7061034",
        "runtime": "2bb946ea4ebb050f6a32f90e979feb975b08280d1ff1aac881dec3d1361ad84d",
    },
    "aarch64": {
        "app": "b5116b67092a6d3bdeb202a0308c2d2ec8f53b980e75e88992781a01aa8937c0",
        "runtime": "c3daeced6f88f9c4ffc4f88c798c48fffd395d873fc0d36b7fc73b753d7f59c9",
    },
}[ARCH]


def command(args, timeout=180):
    began = time.monotonic()
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        def tail(value):
            return (value.decode(errors='replace') if isinstance(value, bytes) else value or '')[-10000:]
        PROGRESS['timedOutCommand'] = {
            'argv': args, 'timeoutSeconds': timeout,
            'elapsedSeconds': round(time.monotonic() - began, 3),
            'stdout': tail(error.stdout), 'stderr': tail(error.stderr),
        }
        raise
    if p.returncode:
        raise RuntimeError(
            str(args)
            + " exit="
            + str(p.returncode)
            + ": "
            + p.stdout[-10000:]
            + p.stderr[-5000:]
        )
    return p.stdout.strip()


def flat(*args, timeout=180):
    return command(["/usr/bin/flatpak", *args], timeout)


def execute(*args, timeout=60):
    return flat(
        "run",
        "--die-with-parent",
        "--env=STNOUPGRADE=1",
        "--command=syncthing",
        APP,
        *args,
        timeout=timeout
    )


def wait(check, description):
    end = time.monotonic() + 90
    last = None
    while time.monotonic() < end:
        try:
            result = check()
            if result:
                return result
        except (OSError, ValueError, KeyError) as error:
            last = str(error)
        time.sleep(0.15)
    raise RuntimeError(description + ": " + str(last))


def wait_for_instances():
    """Flatpak's instance registry can briefly outlive the reaped processes."""
    began = time.monotonic()
    def empty():
        instances = flat("ps", "--columns=application", timeout=10).splitlines()
        PROGRESS['remainingFlatpakApplications'] = instances
        return APP not in instances
    wait(empty, "owned Flatpak instance registry cleanup")
    PROGRESS['instanceCleanupElapsedSeconds'] = round(time.monotonic() - began, 3)


def main():
    marker = Path("/framey-owned-vm")
    if (
        os.getuid() != 1100
        or not marker.is_file()
        or marker.read_text() != "Frame Control Flatpak VM v1\n"
    ):
        raise RuntimeError("Only the private Flatpak VM may run this user probe")
    home = Path.home()
    inputs = json.loads(Path("/input/flatpak-inputs.json").read_text())
    install_limit = inputs['timeouts']['installSeconds']
    assert install_limit == (900 if ARCH == 'aarch64' else 300)
    global PROGRESS
    report = {
        "realFrameContacted": False,
        "architecture": os.uname().machine,
        "flatpakVersion": flat("--version"),
        "signedBundlesInstalled": False,
        "packageLaunched": False,
        "actualTwoWaySync": False,
        "installerEnabled": False,
    }
    PROGRESS = report
    assert (
        hashlib.sha256(Path("/input/flathub-key.gpg").read_bytes()).hexdigest()
        == "8bdc20abc4e19c0796460beb5bfe0e7aa4138716999e19c6f2dbdd78cc41aeaa"
    )
    for kind in ("runtime", "app"):
        bundle = home / ("input-" + kind + ".flatpak")
        with bundle.open("wb") as output:
            for chunk in inputs["bundleChunks"][kind]:
                source = Path("/input") / chunk["file"]
                assert (
                    hashlib.file_digest(source.open("rb"), "sha256").hexdigest()
                    == chunk["sha256"]
                )
                with source.open("rb") as data:
                    shutil.copyfileobj(data, output)
        assert (
            hashlib.file_digest(bundle.open("rb"), "sha256").hexdigest()
            == inputs["bundles"][kind]["sha256"]
        )
        variant = GLib.Variant.new_from_bytes(
            GLib.VariantType.new(
                "(a{sv}tayay(a{sv}aya(say)sstayay)aya(uayttay)a(yaytt))"
            ),
            GLib.Bytes.new(bundle.read_bytes()),
            False,
        )
        assert variant.is_normal_form()
        assert bytes(variant.get_child_value(3).unpack()).hex() == EXPECTED[kind]
        included = variant.get_child_value(0).lookup_value(
            "gpg-keys", GLib.VariantType.new("ay")
        )
        assert included is not None
        included_sha = hashlib.sha256(bytes(included.unpack())).hexdigest()
        assert (
            included_sha
            == "8bdc20abc4e19c0796460beb5bfe0e7aa4138716999e19c6f2dbdd78cc41aeaa"
        )
        report[kind + "EmbeddedKeySha256"] = included_sha
        del included, variant
        began = time.monotonic()
        log = flat(
            "install",
            "--user",
            "--assumeyes",
            "--noninteractive",
            "--no-deps",
            "--no-related",
            "--bundle",
            str(bundle),
            timeout=install_limit,
        )
        report[kind + 'InstallElapsedSeconds'] = round(time.monotonic() - began, 3)
        report[kind + "InstallLog"] = log[-1000:]
        bundle.unlink()  # Only the assembled input created by this fixture.
        target = APP if kind == "app" else "runtime/org.gnome.Platform/" + ARCH + "/49"
        actual = flat("info", "--user", "--show-commit", target)
        assert actual == EXPECTED[kind], (kind, actual)
        report[kind + "InstalledCommit"] = actual
        origin = flat("info", "--user", "--show-origin", target)
        configuration = configparser.ConfigParser()
        configuration.read(home / ".local/share/flatpak/repo/config")
        assert configuration['remote "' + origin + '"'].getboolean("gpg-verify") is True
        report[kind + "OriginGpgVerificationEnabled"] = True
    repository = OSTree.Repo.new(
        Gio.File.new_for_path(str(home / ".local/share/flatpak/repo"))
    )
    repository.open(None)
    report["installedSignatures"] = {}
    for kind, commit in EXPECTED.items():
        # Both bundle origins import only the pinned public key. The API checks
        # the installed commit's retained signature, independently of install exit.
        result = repository.verify_commit(
            commit, None, Gio.File.new_for_path("/input/flathub-key.gpg"), None
        )
        assert result is True
        report["installedSignatures"][kind] = True
    report["userOverrides"] = flat("override", "--user", "--show", APP)
    assert not report["userOverrides"]
    report["signedBundlesInstalled"] = True
    report["reportedVersion"] = execute("--version")
    assert "v1.27.3" in report["reportedVersion"]
    info = flat("run", "--command=cat", APP, "/.flatpak-info")
    config = configparser.ConfigParser()
    config.read_string(info)
    assert config["Application"]["name"] == APP
    assert (
        config["Instance"]["app-commit"] == EXPECTED["app"]
        and config["Instance"]["runtime-commit"] == EXPECTED["runtime"]
    )
    outside = os.readlink("/proc/self/ns/mnt")
    inside = flat("run", "--command=readlink", APP, "/proc/self/ns/mnt")
    assert inside != outside
    report.update(
        packageLaunched=True,
        flatpakInfo=info,
        mountNamespaceOutside=outside,
        mountNamespaceInside=inside,
    )
    cases = []
    processes = []
    logs = []
    service = "framey-signed-flatpak-peer.service"
    unit = home / ".config/systemd/user" / service
    unit.parent.mkdir(parents=True, exist_ok=True)
    assert not unit.exists()

    def ctl(*args):
        return command(["systemctl", "--user", *args], timeout=40)

    try:
        for index in range(2):
            directory = home / ".var/app" / APP / "data" / ("peer-" + str(index))
            directory.mkdir(parents=True)
            execute("generate", "--home", str(directory))
            tree = ET.parse(directory / "config.xml")
            root = tree.getroot()
            for node in root.findall("folder"):
                root.remove(node)
            gui = root.find("gui")
            gui.find("address").text = "127.0.0.1:" + str(8384 + index)
            options = root.find("options")
            for node in options.findall("listenAddress"):
                options.remove(node)
            ET.SubElement(options, "listenAddress").text = "tcp://127.0.0.1:" + str(
                22000 + index
            )
            for key, value in {
                "globalAnnounceEnabled": "false",
                "localAnnounceEnabled": "false",
                "relaysEnabled": "false",
                "natEnabled": "false",
                "urAccepted": "-1",
                "autoUpgradeIntervalH": "0",
                "crashReportingEnabled": "false",
                "startBrowser": "false",
            }.items():
                node = options.find(key)
                if node is None:
                    node = ET.SubElement(options, key)
                node.text = value
            files = directory / "private-sync"
            files.mkdir()
            cases.append(
                dict(
                    home=directory,
                    tree=tree,
                    root=root,
                    key=gui.find("apikey").text,
                    device=root.find("device").get("id"),
                    files=files,
                )
            )
        for index, case in enumerate(cases):
            other = cases[1 - index]
            device = ET.SubElement(
                case["root"],
                "device",
                {
                    "id": other["device"],
                    "name": "owned-peer",
                    "compression": "metadata",
                    "introducer": "false",
                    "skipIntroductionRemovals": "false",
                    "introducedBy": "",
                },
            )
            ET.SubElement(device, "address").text = "tcp://127.0.0.1:" + str(
                22001 - index
            )
            folder = ET.SubElement(
                case["root"],
                "folder",
                {
                    "id": "framey-private",
                    "label": "Private actual Flatpak sync",
                    "path": str(case["files"]),
                    "type": "sendreceive",
                    "rescanIntervalS": "1",
                    "fsWatcherEnabled": "false",
                    "ignorePerms": "false",
                    "autoNormalize": "true",
                },
            )
            for peer in cases:
                ET.SubElement(
                    folder, "device", {"id": peer["device"], "introducedBy": ""}
                )
            case["tree"].write(
                case["home"] / "config.xml", encoding="utf-8", xml_declaration=True
            )
            log = (home / ("peer-" + str(index) + ".log")).open("w+")
            logs.append(log)
            argv = [
                "/usr/bin/flatpak",
                "run",
                "--die-with-parent",
                "--env=STNOUPGRADE=1",
                "--command=syncthing",
                APP,
                "serve",
                "--home",
                str(case["home"]),
                "--no-browser",
                "--no-restart",
                "--no-upgrade",
            ]
            if index == 0:
                unit.write_text(
                    "[Unit]\nDescription=Private signed Flatpak package fixture\n[Service]\nExecStart="
                    + " ".join(argv)
                    + "\nTimeoutStopSec=25\n"
                )
                ctl("daemon-reload")
                ctl("start", service)
                report["serviceMainPid"] = int(
                    ctl("show", service, "--property=MainPID", "--value")
                )
                assert report["serviceMainPid"] > 0
            else:
                process = subprocess.Popen(
                    argv, stdout=log, stderr=log, start_new_session=True
                )
                processes.append(process)

        def api(index, path, method="GET", authenticated=True):
            request = urllib.request.Request(
                "http://127.0.0.1:" + str(8384 + index) + path,
                headers={"X-API-Key": cases[index]["key"]} if authenticated else {},
                method=method,
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                data = response.read()
            return json.loads(data) if data.strip() else None

        for index in range(2):
            wait(lambda: api(index, "/rest/system/status"), "packaged peer readiness")
        try:
            api(0, "/rest/system/status", authenticated=False)
        except urllib.error.HTTPError as error:
            assert error.code == 403
            report["apiKeyErrorStatus"] = 403
        else:
            raise RuntimeError("Unauthenticated API accepted")
        # REST readiness alone does not establish a TLS connection to the peer.
        # Keep the observed connection state in partial evidence on timeout.
        def connected():
            statuses = [api(index, "/rest/system/connections") for index in range(2)]
            report["peerConnections"] = statuses
            return all(status.get("connections", {}).get(cases[1-index]["device"], {})
                       .get("connected") is True for index, status in enumerate(statuses))
        wait(connected, "actual signed Flatpak peer connection")
        forward = b"Frame Control actual signed Flatpak forward sync\n"
        reverse = b"Frame Control actual signed Flatpak reverse sync\n"
        (cases[0]["files"] / "forward.txt").write_bytes(forward)
        api(0, "/rest/db/scan?folder=framey-private", "POST")
        wait(
            lambda: (cases[1]["files"] / "forward.txt").is_file()
            and (cases[1]["files"] / "forward.txt").read_bytes() == forward,
            "actual Flatpak forward bytes",
        )
        (cases[1]["files"] / "reverse.txt").write_bytes(reverse)
        api(1, "/rest/db/scan?folder=framey-private", "POST")
        wait(
            lambda: (cases[0]["files"] / "reverse.txt").is_file()
            and (cases[0]["files"] / "reverse.txt").read_bytes() == reverse,
            "actual Flatpak reverse bytes",
        )
        certificate = (cases[0]["home"] / "cert.pem").read_bytes()
        started = time.monotonic()
        ctl("stop", service)
        report["serviceStopElapsedSeconds"] = round(time.monotonic() - started, 3)
        assert ctl("show", service, "--property=MainPID", "--value") == "0"
        assert (cases[0]["home"] / "cert.pem").read_bytes() == certificate
        ctl("start", service)
        new_pid = int(ctl("show", service, "--property=MainPID", "--value"))
        assert new_pid > 0 and new_pid != report["serviceMainPid"]
        wait(lambda: api(0, "/rest/system/status"), "packaged service restart")
        retained = b"actual Flatpak sync retained across service restart\n"
        (cases[0]["files"] / "restart.txt").write_bytes(retained)
        api(0, "/rest/db/scan?folder=framey-private", "POST")
        wait(
            lambda: (cases[1]["files"] / "restart.txt").is_file()
            and (cases[1]["files"] / "restart.txt").read_bytes() == retained,
            "real package sync after restart",
        )
        report.update(
            actualUserServiceLifecycle=True,
            serviceRestartPid=new_pid,
            certificateRetained=True,
            syncRetainedAfterRestart=True,
        )
        report.update(
            actualTwoWaySync=True,
            forwardSha256=hashlib.sha256(forward).hexdigest(),
            reverseSha256=hashlib.sha256(reverse).hexdigest(),
        )
    finally:
        if unit.exists():
            ctl("stop", service)
            assert ctl("show", service, "--property=MainPID", "--value") == "0"
            unit.unlink()
            ctl("daemon-reload")
            report["ownedServiceRemoved"] = True
        forced = False
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=25)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
                    forced = True
        for log in logs:
            log.seek(0)
            print(log.read()[-2500:], flush=True)
            log.close()
        report["ownedProcessesReaped"] = all(p.poll() is not None for p in processes)
        report["forcedTermination"] = forced
    assert not forced
    wait_for_instances()
    report["noOwnedFlatpakInstancesRemain"] = True
    if Path('/input/candidate-inputs.json').exists():
        migration = subprocess.run(
            ['python3', '/input/syncthing_migration.py'],
            capture_output=True, text=True, timeout=360,
        )
        print(migration.stdout, flush=True)
        print(migration.stderr[-12000:], flush=True)
        lines = [line.partition('FRAMEY_MIGRATION_JSON=')[2]
                 for line in migration.stdout.splitlines() if 'FRAMEY_MIGRATION_JSON=' in line]
        assert migration.returncode == 0 and len(lines) == 1
        report['candidateMigration'] = json.loads(lines[0])
        candidate = subprocess.run(
            ['python3', '/input/syncthing_service.py', '--signed-flatpak'],
            capture_output=True, text=True, timeout=720 if inputs.get('browserSetupRequested') else 360,
        )
        print(candidate.stdout, flush=True)
        print(candidate.stderr[-12000:], flush=True)
        lines = [line.partition('FRAMEY_USER_SERVICE_JSON=')[2]
                 for line in candidate.stdout.splitlines()
                 if 'FRAMEY_USER_SERVICE_JSON=' in line]
        assert candidate.returncode == 0 and len(lines) == 1
        report['candidateService'] = json.loads(lines[0])
        wait_for_instances()
        report['candidateInputs'] = json.loads(Path('/input/candidate-inputs.json').read_text())
    marker = home / ".var/app" / APP / "preserved-owned-marker"
    marker.write_text("private fixture data")
    flat("uninstall", "--user", "--assumeyes", "--noninteractive", APP, timeout=120)
    assert marker.read_text() == "private fixture data"
    if 'candidateService' in report:
        candidate = report['candidateService']
        runtime = Path(candidate['defaultConfigPath']).parent
        assert hashlib.sha256((runtime / 'cert.pem').read_bytes()).hexdigest() == candidate['retainedCertificateSha256']
        assert (runtime / 'owned-marker').read_text() == 'retain private runtime'
        assert hashlib.sha256((runtime / 'sync/reverse.txt').read_bytes()).hexdigest() == candidate['reverseSha256']
        report['uninstallPreservedCandidateData'] = True
    if 'candidateMigration' in report:
        migration = report['candidateMigration']
        runtime = Path(migration['retainedRuntime'])
        assert all(hashlib.sha256((runtime / name).read_bytes()).hexdigest() == expected
                   for name, expected in migration['retainedFilesSha256'].items())
        report['uninstallPreservedMigrationData'] = True
    report["uninstallPreservedOwnedData"] = True
    print("FRAMEY_FLATPAK_USER_JSON=" + json.dumps(report), flush=True)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        print("FRAMEY_FLATPAK_PROGRESS_JSON=" + json.dumps(PROGRESS), flush=True)
        raise
