#!/usr/bin/env python3
"""Pack the built Framey settings sample and check it locally before publication.

No build, downloads, installation, store publication or headset access.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ('plugin.json', 'main.py', 'py_modules/framey_decky_ipc.py', 'dist/index.js')

spec = importlib.util.spec_from_file_location('framey_check_archive', ROOT / 'scripts/framey-check-archive.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def pack(source, output, name):
    # Do not allow a mistyped output path to replace one of the sample inputs.
    if output.resolve() in {(source / member).resolve() for member in FILES}:
        raise ValueError('Output must not replace a sample source file')
    temporary = None
    try:
        # Keep staging beside the destination for an atomic replacement. Close
        # the handle before opening the ZIP so this also works on Windows.
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix='.framey-pack-',
                                         suffix='.zip', delete=False) as handle:
            temporary = Path(handle.name)
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_STORED) as archive:
            for member in FILES:
                entry = zipfile.ZipInfo('framey-settings/' + member, (1980, 1, 1, 0, 0, 0))
                entry.create_system = 3
                entry.external_attr = 0o100644 << 16
                archive.writestr(entry, (source / member).read_bytes())
        result = checker.check(temporary, name)
        if not (result['installerAccepted'] and result['panelCandidate']):
            raise ValueError(result['note'])
        temporary.replace(output)
        return dict(result, output=str(output.resolve()))
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='destination ZIP; parent directory must exist')
    parser.add_argument('--source', type=Path, default=ROOT / 'examples/framey-settings',
                        help='sample directory with plugin.json, main.py and built dist/index.js')
    parser.add_argument('--name', default='Framey Settings Sample',
                        help='exact expected store name (default: Framey Settings Sample)')
    args = parser.parse_args(argv)
    try:
        result = pack(args.source, args.output, args.name)
    except (OSError, ValueError, UnicodeError, RuntimeError, NotImplementedError,
            zipfile.BadZipFile) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
