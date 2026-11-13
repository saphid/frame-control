#!/usr/bin/env python3
"""Bind an independent installer audit report to the exact draft being published."""

import json
import re
import runpy
import sys
from pathlib import Path


INSTALLERS = runpy.run_path(str(Path(__file__).with_name('release-checksums.py')))['INSTALLERS']
APPIMAGE_LAUNCH = 'HTTP 200; FrameControl/1; server stopped'


def verify(report, release, tag):
    if not isinstance(report, dict) or not isinstance(release, dict):
        raise ValueError('audit report or release is not an object')
    if (report.get('tag') != tag or report.get('releaseId') != release.get('id')
            or report.get('draftAtAudit') is not True or release.get('draft') is not True):
        raise ValueError('audit report does not identify this exact draft and tag')
    audited_tag = report.get('tagNameAtAudit')
    if audited_tag not in (tag, release.get('tag_name')) and not (
            isinstance(audited_tag, str) and audited_tag.startswith('untagged-')):
        raise ValueError('audit report has a different tag name')
    if report.get('updateManifest') is not None:
        raise ValueError('audit report was not made against a draft')

    assets = release.get('assets')
    if not isinstance(assets, list):
        raise ValueError('release assets are missing')
    by_name = {asset.get('name'): asset for asset in assets if isinstance(asset, dict)}
    if len(by_name) != len(assets):
        raise ValueError('release assets have duplicate or invalid names')
    if set(by_name) - set(INSTALLERS) - {'SHA256SUMS', 'update.json'}:
        raise ValueError('release has assets outside the audited installer set')
    sums = by_name.get('SHA256SUMS') or {}
    sums_digest = sums.get('digest') or ''
    if (not re.fullmatch(r'sha256:[0-9a-fA-F]{64}', sums_digest)
            or report.get('sha256sumsSha256') != sums_digest[7:].lower()):
        raise ValueError('audited SHA256SUMS differs from the draft')

    rows = report.get('assets')
    if not isinstance(rows, list) or len(rows) != len(INSTALLERS):
        raise ValueError('audit report must cover all ten installers')
    names = [row.get('name') if isinstance(row, dict) else None for row in rows]
    if names != list(INSTALLERS):
        raise ValueError('audit report has missing, duplicate, or reordered installers')
    version = tag.removeprefix('v')
    for row in rows:
        name = row['name']
        asset = by_name.get(name) or {}
        digest = str(asset.get('digest') or '')
        if (not re.fullmatch(r'sha256:[0-9a-fA-F]{64}', digest)
                or type(asset.get('size')) is not int or asset['size'] <= 0
                or row.get('sha256') != digest[7:].lower()
                or row.get('size') != asset['size']):
            raise ValueError(f'audited installer differs from draft: {name}')
        if name.endswith('.dmg'):
            good = row.get('udifTrailer') == 'ok'
        elif name.endswith('.zip'):
            good = row.get('zipCrc') == 'ok' and type(row.get('members')) is int and row['members'] > 0
            if '-mac-' in name:
                good = good and row.get('bundleVersion') == version
        elif name.endswith('.exe'):
            good = row.get('peMachine') in (0x14C, 0x8664)
        elif name.endswith('.AppImage'):
            good = row.get('elfMachine') == (183 if 'arm64' in name else 62)
            if 'x86_64' in name:
                good = good and row.get('appimageLaunch') == APPIMAGE_LAUNCH
        elif name.endswith('.deb'):
            good = (row.get('debVersion') == version
                    and row.get('architecture') == ('arm64' if 'arm64' in name else 'amd64'))
        else:
            good = False
        if not good:
            raise ValueError(f'audit report lacks package or launch verification: {name}')


def main(argv):
    if len(argv) != 4:
        raise ValueError('usage: verify-release-asset-audit.py REPORT.json RELEASE.json TAG')
    report = json.loads(Path(argv[1]).read_text(encoding='utf-8'))
    release = json.loads(Path(argv[2]).read_text(encoding='utf-8'))
    verify(report, release, argv[3])
    print(f'independent installer audit passed for {argv[3]} and draft {release["id"]}')


if __name__ == '__main__':
    try:
        main(sys.argv)
    except (OSError, ValueError) as error:
        sys.exit(f'asset audit gate failed: {error}')
