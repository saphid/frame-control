#!/usr/bin/env python3
"""Verify the shipped settings sample in isolated native published Decky 3.3.0."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--loader', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    native = module('sample_native_inputs', ROOT/'scripts/framey-test-decky-runtime.py')
    packer = module('sample_packer', ROOT/'scripts/framey-pack-sample.py')
    loader, loader_digest = native.loader_bytes(args.loader)
    inputs = ['scripts/framey-test-sample-runtime.py', 'scripts/framey-test-decky-runtime.py',
              'scripts/framey-pack-sample.py', 'scripts/framey-check-archive.py',
              'tests/decky-runtime/sample_settings.py', 'tests/decky-runtime/Containerfile',
              'tests/decky-runtime/check.py', 'tests/decky-runtime/runtime_console.py',
              'tests/decky-runtime/timer_lifecycle.py', 'tests/decky-runtime/deck_settings_private.py',
              'tests/framey_official.py', 'ui/frame_decky_store.py', 'ui/frame_decky.py',
              'ui/framey_compatibility.py', 'ui/framey-compatibility.json', 'ui/framey_decky_ipc.py',
              '.github/workflows/framey-sample-runtime.yml']
    inputs += ['examples/framey-settings/'+p for p in packer.FILES]
    report = dict(success=False, architecture=platform.machine(), decky=native.RELEASE,
                  loaderSha256=loader_digest, realFrameContacted=False,
                  sourceSha256={p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in inputs})
    identifier = uuid.uuid4().hex[:12]
    image, container = 'framey-sample:'+identifier, 'framey-sample-'+identifier
    try:
        with tempfile.TemporaryDirectory(prefix='framey-sample-native-') as temp:
            folder = Path(temp)
            folder.chmod(0o755)  # Public loader/archive inputs; private container runs as UID 1100.
            (folder/'PluginLoader').write_bytes(loader)
            packed = packer.pack(ROOT/'examples/framey-settings', folder/'sample.zip', 'Framey Settings Sample')
            (folder/'sample.zip').chmod(0o644)
            report['archiveSha256'] = packed['sha256']
            subprocess.run(['docker', 'build', '-q', '-t', image, '-f',
                            str(ROOT/'tests/decky-runtime/Containerfile'), str(ROOT/'tests/decky-runtime')],
                           check=True, timeout=300)
            command = ['docker', 'run', '--rm', '--name', container, '--network', 'none', '--read-only',
                       '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '128',
                       '--tmpfs', '/tmp:rw,exec,mode=1777',
                       '--tmpfs', '/run/user/1100:rw,uid=1100,gid=1100,mode=700',
                       '--tmpfs', '/home/tester:rw,exec,uid=1100,gid=1100,mode=700',
                       '--mount', f'type=bind,source={ROOT},target=/repo,readonly',
                       '--mount', f'type=bind,source={folder},target=/input,readonly',
                       '--entrypoint', 'python3', image, '/repo/tests/decky-runtime/sample_settings.py']
            result = subprocess.run(command, capture_output=True, text=True, timeout=150)
            report.update(probeExitStatus=result.returncode, stdout=result.stdout, stderr=result.stderr)
            if result.stdout:
                report['probe'] = json.loads(result.stdout)
            if result.returncode:
                raise RuntimeError('Published Decky sample persistence probe failed')
            assert report['probe']['success'] and report['probe']['cleanShutdownVerified']
            report['success'] = True
    except subprocess.TimeoutExpired as error:
        report['timedOut'] = True
        for name in ('stdout', 'stderr'):
            value = getattr(error, name) or b''
            report[name] = value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value
        report['error'] = str(error)
        raise
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        subprocess.run(['docker', 'rm', '-f', '--volumes', container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['docker', 'image', 'rm', image], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2)+'\n')
    print('PASS: native sample settings save, restart, malformed-state refusal and owned shutdown')


if __name__ == '__main__':
    main()
