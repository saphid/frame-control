"""Pinned official Decky store archives used only in disposable test fixtures."""
from pathlib import Path


ROOT = Path(__file__).parent / 'fixtures/framey-official'
PLUGINS = (
    {'id': 14, 'name': 'ProtonDB Badges', 'version': '1.3.4', 'api_version': 2,
     'folder': 'protondb-decky', 'sha256': '90a3453ac02709cad64096e7539fd8141fa56f99ae3441fc24a4990dc9684358'},
    {'id': 123, 'name': 'Steam Status', 'version': '1.2.3', 'api_version': 2,
     'folder': 'steamstatus-decky', 'sha256': '9053308e04a74f44745b45b9f4f50af3673348d367e7b14bacc5677de707ac4e'},
    {'id': 50, 'name': 'Storage Cleaner', 'version': '1.4.0', 'api_version': 1,
     'folder': 'decky-storage-cleaner', 'sha256': '1afa1a6f129c5d419de0e0bf0f6db8d8e50385a5659179346e996031ea372591'},
    {'id': 18, 'name': 'Bluetooth', 'version': '3.1.1', 'api_version': 1,
     'folder': 'Bluetooth', 'sha256': 'f07f7b74f31da15b5e3a8234a3f00faa01365b56b8f496aca7bb79120be7b8a5'},
)


def archive(plugin):
    return (ROOT / f"{plugin['id']}.zip").read_bytes()
