#!/usr/bin/env python3
"""Install CI prerequisites using bounded, signed Ubuntu mirror attempts.

Use private source/list files so a failing runner mirror or third-party source
cannot block the install. Never change the runner's configured repositories.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile

KEYRING = '/usr/share/keyrings/ubuntu-archive-keyring.gpg'
MIRRORS = {
    'amd64': ('https://archive.ubuntu.com/ubuntu',
              'https://mirrors.mit.edu/ubuntu'),
    'arm64': ('https://ports.ubuntu.com/ubuntu-ports',
              'https://mirrors.mit.edu/ubuntu-ports'),
}
# Ubuntu 26.04 can use the optimized x86 architecture. Let APT keep its
# configured architecture list, including the compatible baseline packages.
MIRRORS['amd64v3'] = MIRRORS['amd64']


def install(packages, codename, architecture, run=subprocess.run):
    if architecture not in MIRRORS or not re.fullmatch('[a-z]+', codename):
        raise ValueError('Unsupported Ubuntu release or architecture')
    if not packages or any(not re.fullmatch('[a-z0-9][a-z0-9+.-]*', p) for p in packages):
        raise ValueError('Expected Debian package names')
    if not Path(KEYRING).is_file():
        raise ValueError('Ubuntu archive keyring is required')
    with tempfile.TemporaryDirectory(prefix='framey-ci-apt-') as folder:
        root = Path(folder)
        root.chmod(0o755)
        # apt reuses downloaded archives only after its own hash verification.
        archives = root / 'archives'
        archives.mkdir()
        for number, mirror in enumerate(MIRRORS[architecture]):
            attempt = root / str(number)
            lists = attempt / 'lists'
            lists.mkdir(parents=True)
            source = attempt / 'ubuntu.sources'
            source.write_text(
                'Types: deb\nURIs: ' + mirror + '\n'
                'Suites: ' + codename + ' ' + codename + '-updates ' + codename + '-security\n'
                'Components: main universe\n'
                'Signed-By: ' + KEYRING + '\n')
            options = [
                '-o', 'Dir::Etc::sourcelist=' + str(source),
                '-o', 'Dir::Etc::sourceparts=-',
                '-o', 'Dir::State::lists=' + str(lists),
                '-o', 'Dir::Cache::archives=' + str(archives),
                '-o', 'APT::Update::Error-Mode=any',
                '-o', 'Acquire::Retries=1',
                '-o', 'Acquire::http::Timeout=15',
                '-o', 'Acquire::https::Timeout=15',
            ]
            print('CI Ubuntu packages: attempt %s via %s' % (number + 1, mirror), flush=True)
            try:
                # GNU timeout bounds the complete command and its process group,
                # including DNS waits that APT's transport timeout may not bound.
                run(['timeout', '--kill-after=5s', '90s', 'apt-get', *options, 'update'],
                    check=True)
                run(['timeout', '--kill-after=5s', '180s', 'apt-get', *options,
                     'install', '-y', '--no-install-recommends', *packages],
                    check=True, env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'})
                return
            except subprocess.CalledProcessError as error:
                print('CI Ubuntu mirror attempt failed (exit %s)' % error.returncode, flush=True)
                if number == len(MIRRORS[architecture]) - 1:
                    raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packages', nargs='+')
    args = parser.parse_args()
    release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines()
                   if '=' in line)
    if release.get('ID', '').strip('"') != 'ubuntu':
        parser.error('Only Ubuntu CI runners are supported')
    architecture = subprocess.check_output(['dpkg', '--print-architecture'], text=True).strip()
    install(args.packages, release.get('VERSION_CODENAME', '').strip('"'), architecture)


if __name__ == '__main__':
    main()
