"""Pinned official Decky store archives used only in disposable test fixtures."""
from pathlib import Path


ROOT = Path(__file__).parent / 'fixtures/framey-official'
PLUGINS = (
    {'id': 14, 'name': 'ProtonDB Badges', 'version': '1.3.4',
     'folder': 'protondb-decky', 'sha256': '90a3453ac02709cad64096e7539fd8141fa56f99ae3441fc24a4990dc9684358'},
    {'id': 123, 'name': 'Steam Status', 'version': '1.2.3',
     'folder': 'steamstatus-decky', 'sha256': '9053308e04a74f44745b45b9f4f50af3673348d367e7b14bacc5677de707ac4e'},
)


def archive(plugin):
    return (ROOT / f"{plugin['id']}.zip").read_bytes()
