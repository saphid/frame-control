"""Read-only headset storage inventory, piped over SSH as python3 -.

No recursive size scans, Steam IPC, subprocesses or writes. Manifest sizes are
Steam's recorded content sizes, not filesystem allocation measurements.
"""
import json
import os
from pathlib import Path
import re
import time

HOME = Path.home()
STEAM = HOME / '.local/share/Steam'
MAX_TEXT = 2 * 1024 * 1024
TOOLS = re.compile(r'^(Steam Linux Runtime|Proton|Steamworks Common|FEX$|Lepton Development$)')


def state(error):
    if isinstance(error, PermissionError):
        return 'permission-denied'
    if isinstance(error, FileNotFoundError):
        return 'missing'
    return 'unavailable'


def read_vdf(path):
    """Small strict KeyValues reader; reject truncated/malformed input explicitly."""
    with open(path, encoding='utf-8', errors='strict') as stream:
        text = stream.read(MAX_TEXT + 1)
    if len(text) > MAX_TEXT:
        raise ValueError('metadata too large')
    tokens = []
    pos = 0
    pattern = re.compile(r'\s+|//[^\n]*|"((?:[^"\\]|\\.)*)"|([{}])')
    while pos < len(text):
        match = pattern.match(text, pos)
        if not match:
            raise ValueError('invalid KeyValues')
        pos = match.end()
        if match.group(1) is not None:
            tokens.append(('text', re.sub(r'\\(["\\])', r'\1', match.group(1))))
        elif match.group(2):
            tokens.append(('brace', match.group(2)))
    index = 0

    def pairs(depth=0):
        nonlocal index
        if depth > 20:
            raise ValueError('metadata too deep')
        result = {}
        while index < len(tokens):
            key_type, key = tokens[index]
            index += 1
            if key_type == 'brace' and key == '}':
                if not depth:
                    raise ValueError('unexpected brace')
                return result
            if key_type == 'brace' or index >= len(tokens):
                raise ValueError('missing value')
            value_type, value = tokens[index]
            index += 1
            if value_type == 'brace' and value == '{':
                value = pairs(depth + 1)
            elif value_type == 'brace':
                raise ValueError('missing value')
            if key.lower() in result:
                raise ValueError('duplicate key')
            result[key.lower()] = value
        if depth:
            raise ValueError('unclosed object')
        return result
    return pairs()


def capacity(path):
    try:
        s = os.statvfs(path)
        return {'state': 'ok', 'total': s.f_blocks * s.f_frsize,
                'free': s.f_bavail * s.f_frsize,
                'used': (s.f_blocks - s.f_bfree) * s.f_frsize,
                'filesystem': str(os.stat(path).st_dev)}
    except (OSError, AttributeError) as error:
        return {'state': state(error), 'total': None, 'free': None, 'used': None,
                'filesystem': None}


def inventory(home=None, steam=None):
    home, steam = Path(home or HOME), Path(steam or STEAM)
    paths = [steam]
    discovery = 'ok'
    try:
        folders = read_vdf(steam / 'steamapps/libraryfolders.vdf').get('libraryfolders')
        if not isinstance(folders, dict):
            raise ValueError('missing libraryfolders')
        for key, value in folders.items():
            if not key.isdigit():
                continue
            path = value.get('path') if isinstance(value, dict) else value
            if not isinstance(path, str) or not os.path.isabs(path) or '\x00' in path:
                raise ValueError('invalid library path')
            paths.append(Path(path))
    except OSError as error:
        discovery = state(error)
    except (ValueError, UnicodeError):
        discovery = 'invalid-metadata'
    libraries, seen = [], set()
    for path in paths:
        canonical = os.path.realpath(path)
        if canonical in seen:
            continue
        seen.add(canonical)
        lib = {'path': str(path), 'capacity': capacity(path), 'state': 'ok',
               'apps': [], 'issues': [], 'recordedBytes': 0, 'unknownSizes': 0,
               'gameBytes': 0, 'toolBytes': 0}
        try:
            with os.scandir(path / 'steamapps') as entries:
                manifests = sorted(entry.path for entry in entries
                                   if re.fullmatch(r'appmanifest_\d+\.acf', entry.name))
            for manifest in manifests:
                try:
                    fields = read_vdf(manifest).get('appstate')
                    if not isinstance(fields, dict):
                        raise ValueError('missing AppState')
                    appid = fields.get('appid', '')
                    if not isinstance(appid, str) or not appid.isdigit() or Path(manifest).name != f'appmanifest_{appid}.acf':
                        raise ValueError('invalid appid')
                    name = fields.get('name') or appid
                    if not isinstance(name, str):
                        raise ValueError('invalid name')
                    raw = fields.get('sizeondisk')
                    size = int(raw) if isinstance(raw, str) and raw.isascii() and raw.isdigit() and len(raw) <= 18 else None
                    kind = 'tool' if TOOLS.match(name) else 'game'
                    lib['apps'].append({'appid': appid, 'name': name, 'bytes': size, 'kind': kind})
                    if size is None:
                        lib['unknownSizes'] += 1
                    else:
                        lib['recordedBytes'] += size
                        lib['toolBytes' if kind == 'tool' else 'gameBytes'] += size
                except (OSError, ValueError, UnicodeError) as error:
                    lib['issues'].append({'file': Path(manifest).name,
                                          'state': state(error) if isinstance(error, OSError) else 'invalid-metadata'})
            lib['apps'].sort(key=lambda app: (app['bytes'] is None, -(app['bytes'] or 0), app['name'].lower()))
            if lib['issues']:
                lib['state'] = 'partial'
        except OSError as error:
            lib['state'] = state(error)
        libraries.append(lib)
    return {'time': time.time(), 'home': capacity(home), 'discovery': discovery, 'libraries': libraries}


if __name__ == '__main__':
    print(json.dumps(inventory()))
