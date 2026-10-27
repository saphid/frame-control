"""Small, unprivileged Decky backend for the Framey author example."""
import json
import os
from pathlib import Path
import tempfile
import decky

SETTINGS_SCHEMA = 1


def settings_file():
    # Decky provides this per-plugin path through its official Python module.
    return Path(decky.DECKY_PLUGIN_SETTINGS_DIR) / 'settings.json'


def read_settings():
    try:
        stored = json.loads(settings_file().read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    if not isinstance(stored, dict):
        return {}
    # The first sample release wrote {"enabled": bool} without a schema.
    # Keep reading it; the next save writes the current format.
    schema = stored.get('schema', SETTINGS_SCHEMA)
    if type(schema) is not int or schema != SETTINGS_SCHEMA:
        raise ValueError('Settings were written by an unsupported sample version')
    return stored


class Plugin:
    async def get_setting(self, key: str, default=False):
        if key != 'enabled':
            raise ValueError('Unknown setting')
        value = read_settings().get(key)
        return value if type(value) is bool else default

    async def set_setting(self, key: str, value: bool):
        if key != 'enabled' or type(value) is not bool:
            raise ValueError('Expected an enabled boolean')
        # Refuse to erase settings from a newer plugin after a downgrade.
        read_settings()
        target = settings_file()
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=target.parent,
                                             prefix='.settings-', delete=False) as output:
                temporary = Path(output.name)
                json.dump({'schema': SETTINGS_SCHEMA, 'enabled': value}, output)
                output.write('\n')
            temporary.chmod(0o600)
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return True
