#!/usr/bin/env python3
"""Stage a prepared NxNative game into its running persistent Frame instance.

Run on the build host. Installs immutable, checksum-verified datasets and switches
one pointer after verification. Saves and previous datasets are left intact.
"""
import argparse
import concurrent.futures
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
import tarfile
import uuid


def source_files(build):
    roots = [('dm', build / 'patched_android'), ('vk', build / 'shader/vk'),
             ('font', build / 'font')]
    romfs = sorted((build / 'extract').glob('*/RomFS'))
    if len(romfs) != 1:
        raise ValueError('build folder must contain exactly one extracted RomFS')
    roots.append(('romfs', romfs[-1]))
    result = []
    for folder, root in roots:
        if not root.is_dir():
            raise ValueError('missing ' + str(root))
        for path in sorted(root.rglob('*')):
            if not path.is_file():
                continue
            if folder == 'dm' and not path.name.endswith(('.patched.bin', '.tsv')):
                continue
            if folder == 'vk' and not path.name.endswith(('.spv', '.vk.txt')):
                continue
            relative = folder + '/' + path.relative_to(root).as_posix()
            if any(c in relative for c in '\n\r\\') or '..' in PurePosixPath(relative).parts:
                raise ValueError('unsupported data filename')
            digest = hashlib.sha256()
            with path.open('rb') as src:
                while block := src.read(4 << 20):
                    digest.update(block)
            result.append((relative, path, path.stat().st_size, digest.hexdigest()))
    names = {x[0] for x in result}
    required = {'dm/main.patched.bin', 'dm/subsdk0.patched.bin', 'dm/sdk.patched.bin',
                'font/standard.ttf', 'font/nintendo_ext.ttf'}
    required.update('dm/' + m + '.fixups.tsv' for m in ('main', 'subsdk0', 'sdk'))
    shaders = [n for n in names if n.endswith('.spv')]
    if (not required <= names or not shaders or not any(n.startswith('romfs/') for n in names)
            or any(n[:-4] + '.vk.txt' not in names for n in shaders)):
        raise ValueError('incomplete modules, fonts or shaders')
    return result


def publish_script(package, ext, temporary, final, digest):
    return f'''set -eu
if pidof {package}:game >/dev/null; then echo 'Stop the game process before staging' >&2; exit 1; fi
mkdir -p {temporary}
trap 'rm -rf {temporary}' EXIT
cd {temporary}
tar -xf -
sha256sum -c frame-data.sha256 > verify.log
cd {ext}
if [ -e {final} ]; then
  (cd {final} && sha256sum -c frame-data.sha256 > /dev/null)
  rm -rf {temporary}
else
  mv {temporary} {final}
fi
printf '%s\\n' {digest} > frame-data.current.part
mv frame-data.current.part frame-data.current
'''


def send_archive(ssh, command, files, metadata=()):
    child = subprocess.Popen(ssh + [command], stdin=subprocess.PIPE)
    try:
        # API 30's toybox truncates PAX long paths. GNU long-name records were
        # checked on the actual Frame and preserve the game's full filenames.
        with tarfile.open(fileobj=child.stdin, mode='w|', format=tarfile.GNU_FORMAT,
                          dereference=True) as archive:
            for name, path, _, _ in files:
                archive.add(path, arcname=name, recursive=False)
            for name, data in metadata:
                info = tarfile.TarInfo(name)
                info.size, info.mode = len(data), 0o644
                archive.addfile(info, io.BytesIO(data))
        child.stdin.close()
        if child.wait():
            raise RuntimeError('staging or checksum verification failed; dataset pointer was not changed')
    except BaseException:
        child.stdin.close()
        child.wait()
        raise


def stage(build, title, frame='frame', address=None, jobs=4):
    if not 1 <= jobs <= 8:
        raise ValueError('jobs must be between 1 and 8')
    if not re.fullmatch('[0-9A-Fa-f]{16}', title):
        raise ValueError('title must be a 16-digit title ID')
    package = 'com.nxnative.t' + title.lower()
    options = ['-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
               '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3']
    if address:
        config = subprocess.check_output(['ssh', '-G', frame], text=True)
        values = dict(line.split(' ', 1) for line in config.splitlines() if ' ' in line)
        identity = values.get('hostkeyalias', values['hostname'])
        options += ['-o', 'HostName=' + address, '-o', 'HostKeyAlias=' + identity]
    ssh = ['ssh', *options, frame]
    metadata = subprocess.check_output(ssh + ['cat ' + shlex.quote('Applications/Android/' + package + '/meta.json')])
    meta = json.loads(metadata)
    if meta['package'] != package:
        raise ValueError('installed package mismatch')
    container = 'lepton-steamlaunch-' + str(int(meta['instance']))
    files = source_files(Path(build))
    manifest = json.dumps({'title': title.upper(), 'files': [
        {'path': n, 'size': size, 'sha256': digest} for n, _, size, digest in files
    ]}, sort_keys=True).encode()
    digest = hashlib.sha256(manifest).hexdigest()
    ext = '/sdcard/Android/data/' + package + '/files'
    temporary = ext + '/frame-data/.stage-' + uuid.uuid4().hex
    final = ext + '/frame-data/' + digest
    # Android resolves its own external-data path. Root's tar writes through the
    # emulated storage mapping; app-private saves are never read or written.
    script = publish_script(package, ext, temporary, final, digest)
    command = shlex.join(['podman', 'exec', '-i', container, '/system/bin/sh', '-c', script])
    print(f'Staging {len(files)} files ({sum(x[2] for x in files) / 1e9:.2f} GB), dataset {digest}', flush=True)
    groups, sizes = [[] for _ in range(jobs)], [0] * jobs
    for item in sorted(files, key=lambda x: x[2], reverse=True):
        group = min(range(jobs), key=lambda i: sizes[i])
        groups[group].append(item)
        sizes[group] += item[2]
    upload_script = f'set -eu; mkdir -p {temporary}; cd {temporary}; tar -xf -'
    upload = shlex.join(['podman', 'exec', '-i', container, '/system/bin/sh', '-c', upload_script])
    guard = shlex.join(['podman', 'exec', container, '/system/bin/sh', '-c',
                       f'if pidof {package}:game >/dev/null; then exit 1; fi'])
    subprocess.run(ssh + [guard], check=True)
    try:
        with concurrent.futures.ThreadPoolExecutor(jobs) as executor:
            futures = [executor.submit(send_archive, ssh, upload, group) for group in groups if group]
            for future in futures:
                future.result()
        send_archive(ssh, command, [], [('frame-data.json', manifest), ('frame-data.sha256', ''.join(
            f'{h}  {n}\n' for n, _, _, h in files).encode())])
    except BaseException:
        cleanup = shlex.join(['podman', 'exec', container, 'rm', '-rf', temporary])
        subprocess.run(ssh + [cleanup], check=False)
        raise
    print(json.dumps({'package': package, 'instance': meta['instance'], 'dataset': digest,
                      'files': len(files), 'bytes': sum(x[2] for x in files), 'verified': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('title')
    parser.add_argument('build')
    parser.add_argument('--frame', default='frame')
    parser.add_argument('--address', help='LAN address; still checks the configured host identity')
    parser.add_argument('--jobs', type=int, default=4, help='parallel transfers (1 to 8)')
    args = parser.parse_args()
    stage(args.build, args.title, args.frame, args.address, args.jobs)
