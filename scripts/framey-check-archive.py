#!/usr/bin/env python3
"""Check a local Decky ZIP against Frame Control's Framey archive rules.

This does not install the plugin, contact the store, or prove its UI works in VR.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ui'))
import frame_decky_store


def check(path, name):
    with path.open('rb') as source:
        data = source.read(frame_decky_store.MAX_ZIP + 1)
    if len(data) > frame_decky_store.MAX_ZIP:
        raise ValueError(f'Plugin archive exceeds the {frame_decky_store.MAX_ZIP // (1024 * 1024)} MiB download limit')
    digest = hashlib.sha256(data).hexdigest()
    folder = frame_decky_store.archive_info(data, digest, name)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        manifest_entry = archive.getinfo(folder + '/plugin.json')
        manifest = json.loads(archive.read(manifest_entry))
        entry = folder + '/dist/index.js'
        frontend = next((item for item in archive.infolist() if item.filename == entry and not item.is_dir()), None)
        version = manifest.get('api_version')
        if version is None and frontend is not None:
            with archive.open(frontend) as source:
                legacy = re.match(rb'\s*\(function\s*\(', source.read(256)) is not None
        else:
            legacy = False
        panel_candidate = bool(manifest_entry.file_size <= 16_384 and
                               frontend and 0 < frontend.file_size <= 8 * 1024 * 1024 and
                               ((type(version) is int and version in (1, 2)) or legacy))
    return {'ok': True, 'sha256': digest, 'folder': folder,
            'installerAccepted': True, 'panelCandidate': panel_candidate,
            'note': ('Basic panel files found; frontend startup, backend discovery and VR input still need runtime tests.'
                     if panel_candidate else
                     'Installer accepts this ZIP, but Framey cannot open its frontend as a panel.')}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path, help='local Decky ZIP; no download or install')
    parser.add_argument('--name', required=True, help='plugin name exactly as it will appear in the Decky store')
    args = parser.parse_args(argv)
    try:
        result = check(args.archive, args.name)
    except (OSError, ValueError, UnicodeError, RuntimeError, NotImplementedError,
            zipfile.BadZipFile) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
