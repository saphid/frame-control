#!/usr/bin/env python3
"""Inspect official Decky archives without importing or executing plugin code.

Archives stay in a caller-selected cache. SHA-256 is checked before inspection.
The resulting observations are static evidence, not compatibility guarantees.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import urllib.request
import zipfile

STORE = 'https://plugins.deckbrew.xyz/plugins'
CDN = 'https://cdn.tzatzikiweeb.moe/file/steam-deck-homebrew/versions/'
INIT = '__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit'


def fetch(url, limit):
    request = urllib.request.Request(url, headers={'User-Agent': 'Frame-Control-compatibility-audit'})
    with urllib.request.urlopen(request, timeout=60) as response:
        if int(response.headers.get('Content-Length', '0')) > limit:
            raise ValueError('download exceeds audit size limit')
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('download exceeds audit size limit')
    return data


def inspect(item, cache):
    version = item['versions'][0]
    digest = version['hash']
    result = {'id': item['id'], 'name': item['name'], 'version': version['name'],
              'sha256': digest, 'tags': item.get('tags', [])}
    try:
        path = cache / (digest + '.zip')
        data = path.read_bytes() if path.exists() else fetch(CDN + digest + '.zip', 200 * 1024 * 1024)
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('official archive SHA-256 mismatch')
        path.write_bytes(data)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 6000 or sum(e.file_size for e in entries) > 500 * 1024 * 1024:
                raise ValueError('archive exceeds audit size limit')
            manifests = [e.filename for e in entries if e.filename.count('/') == 1 and e.filename.endswith('/plugin.json')]
            if len(manifests) != 1:
                raise ValueError('expected one top-level plugin.json')
            manifest = json.loads(archive.read(manifests[0]))
            folder = manifests[0].split('/')[0]
            frontend_path = folder + '/dist/index.js'
            frontend = archive.read(frontend_path).decode('utf-8', errors='replace') if frontend_path in archive.namelist() else ''
            result.update(folder=folder, archiveBytes=len(data), api=manifest.get('api_version', 'legacy'), flags=manifest.get('flags', []),
                          modernBridge=INIT in frontend, frontend=bool(frontend),
                          frontendApi=('legacy' if re.match(r'\s*\(function\s*\(', frontend) else
                                       next(iter(re.findall(r'API_VERSION\s*=\s*(\d+)', frontend)), 'unknown')))
            python_files, native, sources = [], [], []
            for entry in entries:
                if entry.is_dir():
                    continue
                with archive.open(entry) as stream:
                    header = stream.read(20)
                if header[:4] == b'\x7fELF':
                    machine = int.from_bytes(header[18:20], 'little' if header[5] == 1 else 'big')
                    native.append({'file': entry.filename, 'elfMachine': machine,
                                   'arch': {62: 'x86_64', 183: 'aarch64', 3: 'x86', 40: 'arm'}.get(machine, str(machine))})
                elif header[:2] == b'MZ':
                    native.append({'file': entry.filename, 'arch': 'Windows'})
                if entry.filename.endswith('.py') and entry.file_size < 2 * 1024 * 1024:
                    python_files.append(entry.filename)
                    sources.append(archive.read(entry).decode('utf-8', errors='replace'))
            backend = '\n'.join(sources)
            metadata = json.dumps(manifest)
            for suffix in ('/package.json', '/README.md'):
                name = folder + suffix
                if name in archive.namelist() and archive.getinfo(name).file_size < 1024 * 1024:
                    metadata += '\n' + archive.read(name).decode('utf-8', errors='replace')
            repositories = set(re.findall(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', metadata + '\n' + backend))
            repositories.update('https://github.com/' + match for match in re.findall(
                r'https://raw\.githubusercontent\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)', metadata))

            result.update(pythonFiles=python_files, native=native,
                          steamClient=sorted(set(re.findall(r'SteamClient\.([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)', frontend))),
                          dfl=sorted(set(re.findall(r'(?:DFL|__DFL__|deckyFrontendLib)\.([A-Za-z_$][\w$]*)', frontend))),
                          globals=sorted(set(re.findall(r'\b(?:Router|routerHook|toaster|SteamUIStore|appStore|appDetailsStore|collectionStore|achievementStore|window\.SP_[A-Z_]+|DeckyPluginLoader|webpackChunksteamui)\b', frontend))),
                          uiSurfaces=[label for label, pattern in (
                              ('local/Steam routes', r'routerHook|addRoute|removeRoute'),
                              ('toasts', r'\btoaster\b|\.toast\('),
                              ('QAM/global tabs', r'quickAccessMenu|addGlobalComponent|addTab|QAM'),
                              ('Steam page patches/module lookup', r'afterPatch|beforePatch|findModule|createModuleMapping'),
                              ('Steam stores', r'\b\w+Store\b'),
                          ) if re.search(pattern, frontend)],
                          hardwareSignals=sorted(set(re.findall(r'(?:/sys/[^\s\x22\x27)]+|/dev/(?:hidraw|input|i2c|drm)[\w/*-]*|\b(?:ryzenadj|intel_pstate|amdgpu|hwmon|gamescope|pactl|bluetoothctl|flatpak|systemctl|sudo|x86_64|amd64)\b)', backend))),
                          sourceURLs=sorted(repositories)[:20])
    except Exception as failure:
        result['auditError'] = str(failure)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, help='saved official catalog (otherwise fetch current)')
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    records = json.loads(args.catalog.read_bytes() if args.catalog else fetch(STORE, 4 * 1024 * 1024))
    records = [r for r in records if r.get('visible') is not False and r.get('versions')]
    args.cache.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=6) as workers:
        plugins = list(workers.map(lambda item: inspect(item, args.cache), records))
    args.output.write_text(json.dumps({'checkedAtUtc': datetime.now(timezone.utc).isoformat(),
        'source': STORE, 'method': 'SHA-256-verified official archives; static inspection only; plugin code was not executed.',
        'plugins': plugins}, indent=2) + '\n')
    print(f"Audited {len(plugins)} official plugins; {sum('auditError' in p for p in plugins)} errors. {args.output}")


if __name__ == '__main__':
    main()
