#!/usr/bin/env python3
"""Verify pinned app payloads offline; this does not prove Flatpak launch.

Requires python3-gi, gir1.2-ostree-1.0 and ostree. Run in the private,
networkless Containerfile.flatpak image with read-only published inputs.
"""
import argparse
import base64
import configparser
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import gi

from gi.repository import Gio, GLib

APP = 'me.kozec.syncthingtk'
COMMITS = {
    'x86_64': '2be395a769ce7f1d8332892c1777d9f1f147ce7f66647864d87d5550e7061034',
    'aarch64': 'b5116b67092a6d3bdeb202a0308c2d2ec8f53b980e75e88992781a01aa8937c0',
}
DESCRIPTOR_SHA256 = '3371dd250e61d9e1633630073fefda153cd4426f72f4afa0c3373ae2e8fea03a'
KEY_SHA256 = '8bdc20abc4e19c0796460beb5bfe0e7aa4138716999e19c6f2dbdd78cc41aeaa'
# Signed x86_64 tree's /files/bin/syncthing content object, used for refusal.
BINARY_OBJECT = 'd32257b286fe812ac1b68c812d2fb233fe35f56e66c0a52703186ec8f551e6dc'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(args):
    result = subprocess.run(args, capture_output=True, timeout=90)
    if result.returncode:
        raise RuntimeError(result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace'))
    return result.stdout


def signatures(path, commit):
    gi.require_version('OSTree', '1.0')
    from gi.repository import OSTree

    repository = OSTree.Repo.new(Gio.File.new_for_path(str(path)))
    repository.open(None)
    result = repository.verify_commit_for_remote(commit, 'flathub', None)
    if not result.require_valid_signature() or result.count_valid() < 1:
        raise RuntimeError('No valid Flathub signature')
    return {'validSignatures': result.count_valid(), 'allSignatures': result.count_all()}


def verify(objects, descriptor):
    descriptor_bytes = descriptor.read_bytes()
    if sha(descriptor_bytes) != DESCRIPTOR_SHA256:
        raise ValueError('Unexpected Flathub descriptor')
    config = configparser.ConfigParser()
    config.read_string(descriptor_bytes.decode())
    key = base64.b64decode(config['Flatpak Repo']['GPGKey'], validate=True)
    if sha(key) != KEY_SHA256:
        raise ValueError('Unexpected Flathub public key')
    entries = list(objects.rglob('*'))
    total = 0
    if len(entries) > 10512:
        raise ValueError('Too many cached object entries')
    for path in entries:
        relative = path.relative_to(objects)
        if path.is_symlink() or len(relative.parts) > 2:
            raise ValueError('Unexpected object cache path')
        if path.is_file():
            checksum, separator, kind = path.name.partition('.')
            if len(relative.parts) != 2 or len(relative.parts[0] + checksum) != 64 or not separator or kind not in ('commit', 'commitmeta', 'dirtree', 'dirmeta', 'filez') or any(c not in '0123456789abcdef' for c in relative.parts[0] + checksum):
                raise ValueError('Unexpected cached object name')
            size = path.stat().st_size
            total += size
            if size > 64 * 1024 * 1024 or total > 256 * 1024 * 1024:
                raise ValueError('Object cache exceeds bound')
    report = {
        'descriptorSha256': sha(descriptor_bytes), 'keySha256': sha(key),
        'verifierSha256': sha(Path(__file__).read_bytes()),
        'payloadIntegrityVerified': False, 'packageInstalled': False,
        'packageLaunched': False, 'realFrameContacted': False,
        'architectures': {}, 'negativeControls': {},
    }
    with tempfile.TemporaryDirectory(prefix='framey-flatpak-verify-') as temp:
        root = Path(temp)
        repo = root / 'repo'
        key_path = root / 'flathub.gpg'
        key_path.write_bytes(key)
        command = ['ostree', '--repo=' + str(repo)]
        run(command + ['init', '--mode=archive-z2'])
        run(command + ['remote', 'add', '--gpg-import=' + str(key_path),
                       'flathub', 'https://dl.flathub.org/repo/'])
        (repo / 'objects').rmdir()
        (repo / 'objects').symlink_to(objects.resolve(), target_is_directory=True)
        for arch, commit in COMMITS.items():
            data = (objects / commit[:2] / (commit[2:] + '.commit')).read_bytes()
            if sha(data) != commit:
                raise ValueError('Commit content checksum mismatch')
            value = GLib.Variant.new_from_bytes(
                GLib.VariantType.new('(a{sv}aya(say)sstayay)'), GLib.Bytes.new(data), False)
            if not value.is_normal_form():
                raise ValueError('Invalid commit encoding')
            metadata = value.unpack()[0]
            ref = 'app/' + APP + '/' + arch + '/stable'
            if metadata['ostree.ref-binding'] != [ref] or metadata['ostree.collection-binding'] != 'org.flathub.Stable':
                raise ValueError('Unexpected signed app binding')
            entry = {'commit': commit, 'ref': ref, 'metadata': metadata['xa.metadata'],
                     'signatureValidity': signatures(repo, commit)}
            report['architectures'][arch] = entry
            run(command + ['refs', '--create=' + ref, commit])
        report['fsck'] = run(command + ['fsck', '--all', '--verify-bindings']).decode()
        for arch, commit in COMMITS.items():
            entry = report['architectures'][arch]
            manifest = run(command + ['cat', commit, '/files/manifest.json'])
            entry['manifestSha256'] = sha(manifest)
            modules = json.loads(manifest)['modules']
            syncthing = next(module for module in modules if isinstance(module, dict) and module.get('name') == 'syncthing')
            entry['syncthingSource'] = [source for source in syncthing['sources'] if source['type'] == 'archive']
            binary = run(command + ['cat', commit, '/files/bin/syncthing'])
            machine = int.from_bytes(binary[18:20], 'little')
            if binary[:4] != b'\x7fELF' or machine != {'x86_64': 62, 'aarch64': 183}[arch]:
                raise ValueError('Unexpected packaged Syncthing architecture')
            entry.update(binarySha256=sha(binary), binaryBytes=len(binary), elfMachine=machine, binaryExecuted=False)
        # Tamper only with a disposable copy. CLI show is informational: it can
        # exit zero for a BAD signature, so require libostree's validity result.
        negative = root / 'negative'
        shutil.copytree(repo, negative, symlinks=True)
        (negative / 'objects').unlink()
        shutil.copytree(objects, negative / 'objects')
        for arch, commit in COMMITS.items():
            other = next(value for value in COMMITS.values() if value != commit)
            target = negative / 'objects' / commit[:2] / (commit[2:] + '.commitmeta')
            original = target.read_bytes()
            target.write_bytes((negative / 'objects' / other[:2] / (other[2:] + '.commitmeta')).read_bytes())
            try:
                shown = subprocess.run(['ostree', '--repo=' + str(negative), 'show',
                                        '--gpg-verify-remote=flathub', commit], capture_output=True, timeout=30)
                try:
                    signatures(negative, commit)
                except GLib.Error as error:
                    report['negativeControls'][arch + 'WrongSignature'] = {
                        'rejected': True, 'cliExitCode': shown.returncode, 'validityError': str(error)}
                else:
                    raise RuntimeError('Swapped signature accepted')
            finally:
                target.write_bytes(original)
        target = negative / 'objects' / BINARY_OBJECT[:2] / (BINARY_OBJECT[2:] + '.filez')
        original = target.read_bytes()
        changed = bytearray(original)
        changed[-1] ^= 1
        target.write_bytes(changed)
        try:
            checked = subprocess.run(['ostree', '--repo=' + str(negative), 'fsck', '--all', '--verify-bindings'],
                                     capture_output=True, text=True, timeout=90)
            if checked.returncode == 0:
                raise RuntimeError('Corrupted content accepted')
            report['negativeControls']['corruptBinaryContent'] = {
                'rejected': True, 'exitCode': checked.returncode, 'stderr': checked.stderr[-3000:]}
        finally:
            target.write_bytes(original)
        run(['ostree', '--repo=' + str(negative), 'fsck', '--all', '--verify-bindings'])
        report['negativeControls']['restoredStorePassed'] = True
        report['payloadIntegrityVerified'] = True
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--objects', type=Path, required=True)
    parser.add_argument('--descriptor', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.objects, args.descriptor), indent=2), flush=True)


if __name__ == '__main__':
    main()
