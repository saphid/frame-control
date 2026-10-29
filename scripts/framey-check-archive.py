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

API_V1_MARKER = b'__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit'


def api_v1_bridge(archive, folder, bundle):
    """Mirror the API v1 initializer/chunk admission in framey_panel._owned_dist."""
    if API_V1_MARKER in bundle:
        return True
    if b'./chunks/' not in bundle:
        return False
    prefix = folder + '/dist/chunks/'
    children = {}
    for item in archive.infolist():
        if not item.filename.startswith(prefix):
            continue
        tail = item.filename[len(prefix):]
        if not tail:
            continue
        child = tail.split('/')[0]
        if '/' in tail:
            children.setdefault(child, None)  # A directory, not a direct JS chunk.
        else:
            children[child] = item
    if len(children) > 128:
        return False
    supported = False
    for item in children.values():
        if item is None or item.is_dir() or not item.filename.endswith('.js'):
            continue
        if item.file_size > 8 * 1024 * 1024:
            return False
        if API_V1_MARKER in archive.read(item):
            supported = True
    return supported


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
        bundle = b''
        if frontend is not None and 0 < frontend.file_size <= 8 * 1024 * 1024:
            with archive.open(frontend) as source:
                bundle = source.read()
        legacy = re.match(rb'\s*\(function\s*\(', bundle) is not None
        frontend_api = (version == 2 or
                        (version == 1 and (legacy or api_v1_bridge(archive, folder, bundle))) or
                        (version is None and legacy))
        panel_candidate = bool(manifest_entry.file_size <= 16_384 and
                               frontend and 0 < frontend.file_size <= 8 * 1024 * 1024 and
                               type(version) in (int, type(None)) and frontend_api)
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
