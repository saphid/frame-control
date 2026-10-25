#!/usr/bin/env python3
"""Audit a verified catalog cache in a private disposable fake-Frame project."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    cache = args.cache.resolve()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    records = json.loads((root/'ui/framey-compatibility.json').read_text())['plugins']
    if not all((cache/(p['sha256']+'.zip')).is_file() for p in records):
        parser.error('cache must contain all exact catalog archives; run framey-audit-store.py first')
    # Unique project avoids tearing down another job's fake Frame or its volumes.
    project = 'framey-catalog-'+uuid.uuid4().hex[:10]
    subprocess.run(['docker', 'build', '-q', '-t', 'fakeframe-frame', '-f',
                    str(root/'tests/fakeframe/Containerfile'), str(root/'tests/fakeframe')], check=True)
    subprocess.run(['docker', 'build', '-q', '-t', 'fakeframe-host', '-f',
                    str(root/'tests/fakeframe/host.Containerfile'), str(root/'tests/fakeframe')], check=True)
    with tempfile.TemporaryDirectory(prefix='framey-catalog-') as temp:
        override = Path(temp)/'compose.json'
        override.write_text(json.dumps({'services': {'host': {
            'volumes': [f'{cache}:/audit-cache:ro', f'{output.parent}:/audit-output'],
            'environment': {'FRAMEY_AUDIT_CACHE': '/audit-cache',
                            'FRAMEY_AUDIT_OUTPUT': '/audit-output/'+output.name}}}}))
        compose = ['docker', 'compose', '-p', project, '-f', str(root/'tests/fakeframe/compose.yaml'), '-f', str(override)]
        try:
            subprocess.run(compose+['up', '-d', '--wait'], check=True)
            subprocess.run(compose+['exec', '-T', '-w', '/repo/tests/e2e', 'host', 'python3', '-m',
                'unittest', '-v', 'test_framey_catalog.CatalogAudit'], check=True)
        finally:
            subprocess.run(compose+['down', '-v', '--remove-orphans'], check=True)


if __name__ == '__main__':
    main()
