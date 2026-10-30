"""Bootstrap only the marked disposable package VM, never the host."""

import json
import os
import subprocess
import traceback
from pathlib import Path

if (
    os.getuid() != 0
    or os.getpid() == 1
    or not Path("/framey-owned-vm").is_file()
    or Path("/framey-owned-vm").read_text() != "Frame Control Flatpak VM v1\n"
):
    raise RuntimeError("Only the private Flatpak VM may run this bootstrap")
report = {"success": False, "realFrameContacted": False, "hostBusExposed": False}
browser = False
try:
    assert Path("/proc/1/comm").read_text().strip() == "systemd"
    # Separate bounded guest-only data filesystem; retain OSTree's default
    # 500MB free-space requirement instead of weakening its protection.
    subprocess.run(
        [
            "mount",
            "-t",
            "tmpfs",
            "-o",
            "size=3584m,uid=1100,gid=1100,mode=700",
            "tmpfs",
            "/home/tester",
        ],
        check=True,
        timeout=15,
    )
    subprocess.run(["systemctl", "start", "user@1100.service"], check=True, timeout=40)
    user = [
        "runuser",
        "-u",
        "tester",
        "--",
        "env",
        "XDG_RUNTIME_DIR=/run/user/1100",
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1100/bus",
    ]
    limits = json.loads(Path('/input/flatpak-inputs.json').read_text())['timeouts']
    browser = json.loads(Path('/input/flatpak-inputs.json').read_text()).get('browserSetupRequested', False)
    assert not browser or os.uname().machine == 'x86_64'
    expected_user_limit = 1440 if browser else (2400 if os.uname().machine == 'aarch64' else 840)
    assert limits['userSeconds'] == expected_user_limit
    result = subprocess.run(
        user + ["python3", "/framey-user.py"],
        capture_output=True,
        text=True,
        timeout=limits['userSeconds'],
    )
    print(result.stdout, flush=True)
    print(result.stderr[-12000:], flush=True)
    partial = [
        line.partition("FRAMEY_FLATPAK_PROGRESS_JSON=")[2]
        for line in result.stdout.splitlines()
        if "FRAMEY_FLATPAK_PROGRESS_JSON=" in line
    ]
    if partial:
        report["partial"] = json.loads(partial[-1])
    lines = [
        line.partition("FRAMEY_FLATPAK_USER_JSON=")[2]
        for line in result.stdout.splitlines()
        if "FRAMEY_FLATPAK_USER_JSON=" in line
    ]
    assert result.returncode == 0 and len(lines) == 1
    report.update(
        pid1="systemd",
        userBusPresent=Path("/run/user/1100/bus").exists(),
        flatpak=json.loads(lines[0]),
    )
    subprocess.run(["systemctl", "stop", "user@1100.service"], check=True, timeout=40)
    report["success"] = True
except BaseException:
    report["success"] = False
    traceback.print_exc()
    subprocess.run(["journalctl", "-b", "--no-pager", "-n", "100"], timeout=20)
if browser:
    # A separate owned write-only channel avoids journald/console loss and
    # interleaving. Never reconstruct success from partial log fragments.
    import sys
    sys.path.insert(0, '/input')
    from guest_result import PORT, write_result
    ports = [p for p in Path('/sys/class/virtio-ports').glob('vport*p*')
             if (p/'name').read_text().strip() == PORT]
    assert len(ports) == 1, 'Dedicated guest result port unavailable'
    with (Path('/dev')/ports[0].name).open('wb', buffering=0) as stream:
        write_result(stream, report)
else:
    print("FRAMEY_SYSTEMD_PROBE_JSON=" + json.dumps(report), flush=True)
subprocess.run(
    [
        "systemd-run",
        "--unit=framey-flatpak-shutdown",
        "--on-active=2",
        "--timer-property=AccuracySec=100ms",
        "/usr/bin/systemctl",
        "poweroff",
    ],
    check=True,
    timeout=15,
)
