#!/usr/bin/env python3
"""Run exact signed Syncthing packages in an owned, networkless native VM.

Inputs are a disposable Debian rootfs export with systemd, Flatpak, OSTree GI
and a kernel, plus locally generated bundles of the pinned published commits.
No host filesystem, bus, disk, device or network NIC is exposed to the guest.
This tests the actual package, not the Framey installer or Decky integration.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ARCHES = {
    "x86_64": ("qemu-system-x86_64", "ttyS0", []),
    "aarch64": ("qemu-system-aarch64", "ttyAMA0", ["-machine", "virt"]),
}
COMMITS = {
    "x86_64": {
        "app": "2be395a769ce7f1d8332892c1777d9f1f147ce7f66647864d87d5550e7061034",
        "runtime": "2bb946ea4ebb050f6a32f90e979feb975b08280d1ff1aac881dec3d1361ad84d",
    },
    "aarch64": {
        "app": "b5116b67092a6d3bdeb202a0308c2d2ec8f53b980e75e88992781a01aa8937c0",
        "runtime": "c3daeced6f88f9c4ffc4f88c798c48fffd395d873fc0d36b7fc73b753d7f59c9",
    },
}
MARKER = b"Frame Control Flatpak VM v1\n"
KEY_SHA256 = "8bdc20abc4e19c0796460beb5bfe0e7aa4138716999e19c6f2dbdd78cc41aeaa"
BUNDLES = {
    "runtime": {
        "sha256": "9e2a88bf95d9a6bdcf15335d967ef2d311946875d241b24f998631bdb1899069",
        "bytes": 292381320,
    },
    "app": {
        "sha256": "25c3368e362634e6cf239bc58663bb8b7ca69b6f5fbfa90ab3b86956c1884a04",
        "bytes": 9872520,
    },
}
REQUIRED = (
    "signedBundlesInstalled",
    "packageLaunched",
    "actualTwoWaySync",
    "runtimeOriginGpgVerificationEnabled",
    "appOriginGpgVerificationEnabled",
    "actualUserServiceLifecycle",
    "certificateRetained",
    "syncRetainedAfterRestart",
    "ownedServiceRemoved",
    "ownedProcessesReaped",
    "noOwnedFlatpakInstancesRemain",
    "uninstallPreservedOwnedData",
)


def sha(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def reap(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)


def prepared_bundles(preparation, arch):
    if (
        preparation.get("architecture") != arch
        or preparation.get("commits") != COMMITS[arch]
        or preparation.get("keySha256") != KEY_SHA256
        or preparation.get("payloadIntegrityVerified") is not True
        or any(
            preparation.get("signatures", {}).get(kind, 0) < 1
            for kind in ("app", "runtime")
        )
    ):
        raise ValueError("Incomplete or mismatched preparation proof")
    bundles = preparation["bundles"]
    if set(bundles) != {"app", "runtime"}:
        raise ValueError("Unexpected prepared bundle set")
    for kind, expected in bundles.items():
        if (
            expected.get("commit") != COMMITS[arch][kind]
            or not 0 < expected.get("bytes", 0) <= 384 * 1024**2
        ):
            raise ValueError("Unexpected prepared bundle commit or size")
    return bundles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rootfs-tar", type=Path, required=True)
    parser.add_argument("--bundles", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New evidence directory; existing directories are refused",
    )
    parser.add_argument(
        "--preparation",
        type=Path,
        help="Offline preparation.json for locally generated exact-commit bundles",
    )
    args = parser.parse_args()
    arch = platform.machine()
    if platform.system() != "Linux" or arch not in ARCHES:
        parser.error("This package probe requires native AMD64 or ARM64 Linux")
    emulator, console_device, machine = ARCHES[arch]
    if shutil.which(emulator) is None:
        parser.error(emulator + " is required")
    if args.rootfs_tar.stat().st_size > 2 * 1024**3:
        parser.error("Guest rootfs exceeds 2 GiB")
    if args.key.stat().st_size > 64 * 1024 or sha(args.key) != KEY_SHA256:
        parser.error("Unexpected Flathub public key")
    payloads = {"flathub-key.gpg": args.key.read_bytes()}
    bundles = BUNDLES
    preparation = None
    if args.preparation:
        if args.preparation.stat().st_size > 256 * 1024:
            parser.error("Oversized preparation report")
        preparation = json.loads(args.preparation.read_text())
        try:
            bundles = prepared_bundles(preparation, arch)
        except ValueError as error:
            parser.error(str(error))
    elif arch != "x86_64":
        parser.error("ARM64 requires an exact signed offline --preparation report")
    manifest = {"bundles": bundles, "bundleChunks": {}}
    for kind, expected in bundles.items():
        path = args.bundles / (kind + ".flatpak")
        if path.stat().st_size != expected["bytes"] or sha(path) != expected["sha256"]:
            parser.error("Unexpected pinned " + kind + " bundle")
        chunks = []
        with path.open("rb") as source:
            while data := source.read(64 * 1024**2):
                name = f"{kind}.part-{len(chunks):03}"
                payloads[name] = data
                chunks.append(
                    {"file": name, "sha256": hashlib.sha256(data).hexdigest()}
                )
        manifest["bundleChunks"][kind] = chunks
    payloads["flatpak-inputs.json"] = json.dumps(manifest).encode()
    assert sum(map(len, payloads.values())) < 384 * 1024**2
    args.output.mkdir(parents=True, exist_ok=False)
    packer_path = ROOT / "scripts/framey-test-syncthing-service.py"
    root_probe = ROOT / "tests/decky-runtime/syncthing_flatpak_package_root.py"
    user_probe = ROOT / "tests/decky-runtime/syncthing_flatpak_package.py"
    source_paths = [Path(__file__).resolve(), packer_path, root_probe, user_probe]
    fingerprints = {str(path.relative_to(ROOT)): sha(path) for path in source_paths}
    spec = importlib.util.spec_from_file_location("service_vm", packer_path)
    packer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packer)
    rootfs_sha = sha(args.rootfs_tar)
    kernel = packer.pack(
        args.rootfs_tar,
        args.output / "initrd.gz",
        payloads,
        marker=MARKER,
        bootstrap=root_probe.read_bytes(),
        user_probe=user_probe.read_bytes(),
        normal_root=True,
        timeout=900,
    )
    (args.output / "vmlinuz").write_bytes(kernel)
    inputs = {
        "rootfsTarSha256": rootfs_sha,
        "rootfsTarBytes": args.rootfs_tar.stat().st_size,
        "kernelSha256": hashlib.sha256(kernel).hexdigest(),
        "initrdSha256": sha(args.output / "initrd.gz"),
        "sourceSha256": fingerprints,
        "bundles": bundles,
        "architecture": arch,
        "preparationSha256": sha(args.preparation) if args.preparation else None,
        "keySha256": KEY_SHA256,
        "memoryMiB": 6144,
        "timeoutSeconds": 960,
        "networkDevice": False,
        "hostBusExposed": False,
        "realFrameContacted": False,
    }
    (args.output / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    command = [
        emulator,
        *machine,
        "-accel",
        "tcg,thread=multi",
        "-cpu",
        "max",
        "-smp",
        "2",
        "-m",
        "6144",
        "-nodefaults",
        "-nographic",
        "-serial",
        "stdio",
        "-monitor",
        "none",
        "-nic",
        "none",
        "-no-reboot",
        "-kernel",
        str(args.output / "vmlinuz"),
        "-initrd",
        str(args.output / "initrd.gz"),
        "-append",
        f"console={console_device} rdinit=/init panic=-1 systemd.show_status=false",
    ]
    console = args.output / "console.log"
    result = {"success": False, "inputs": inputs}
    try:
        with console.open("w") as log:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                code = process.wait(timeout=960)
            finally:
                reap(process)
                result["ownedQemuReaped"] = process.poll() is not None
        lines = [
            line.partition("FRAMEY_SYSTEMD_PROBE_JSON=")[2]
            for line in console.read_text().splitlines()
            if "FRAMEY_SYSTEMD_PROBE_JSON=" in line
        ]
        if code != 0 or len(lines) != 1:
            raise RuntimeError("Missing/ambiguous guest result or nonzero QEMU exit")
        guest = json.loads(lines[0])
        result["guest"] = guest
        package = guest.get("flatpak", {})
        if package.get("architecture") != arch:
            raise RuntimeError("Guest architecture does not match the native host")
        if guest.get("success") is not True or any(
            package.get(key) is not True for key in REQUIRED
        ):
            raise RuntimeError(
                "Incomplete package probe; inspect retained guest result and console"
            )
        if (
            package.get("forcedTermination") is not False
            or package.get("apiKeyErrorStatus") != 403
        ):
            raise RuntimeError("Package cleanup/authentication gate failed")
        if any(
            sha(path) != fingerprints[str(path.relative_to(ROOT))]
            for path in source_paths
        ):
            raise RuntimeError("Probe sources changed during execution")
        if args.preparation and sha(args.preparation) != inputs["preparationSha256"]:
            raise RuntimeError("Preparation changed during execution")
        if sha(args.rootfs_tar) != rootfs_sha:
            raise RuntimeError("Guest rootfs changed during execution")
        result["success"] = True
    except BaseException as error:
        result["error"] = str(error)
        raise
    finally:
        (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
