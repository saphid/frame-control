"""Small, unprivileged Decky backend for the Framey author example."""
import json
import os
from pathlib import Path
import tempfile
import decky


def settings_file():
    # Decky provides this per-plugin path through its official Python module.
    return Path(decky.decky_SETTINGS_DIR) / 'settings.json'


class Plugin:
    async def get_setting(self, key: str, default=False):
        if key != 'enabled':
            raise ValueError('Unknown setting')
        try:
            stored = json.loads(settings_file().read_text(encoding='utf-8'))
        except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
            return default
        value = stored.get(key) if isinstance(stored, dict) else None
        return value if type(value) is bool else default

    async def set_setting(self, key: str, value: bool):
        if key != 'enabled' or type(value) is not bool:
            raise ValueError('Expected an enabled boolean')
        target = settings_file()
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=target.parent,
                                             prefix='.settings-', delete=False) as output:
                temporary = Path(output.name)
                json.dump({'enabled': value}, output)
                output.write('\n')
            temporary.chmod(0o600)
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return True
