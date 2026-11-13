"""Small, local Frame Control extensions. Code runs only in a sandboxed iframe."""
import json
import re
from pathlib import Path

import frame_host


ID = re.compile(r"[a-z][a-z0-9-]{0,39}\Z")
API_VERSION = 1
ASSET = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".json": "application/json",
         ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
         ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml"}


def root():
    return frame_host.data_dir("extensions")


def _manifest(folder):
    if folder.is_symlink() or not ID.fullmatch(folder.name):
        raise ValueError("invalid extension directory")
    manifest = folder / "manifest.json"
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size > 16_384:
        raise ValueError("missing or oversized manifest.json")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("id") != folder.name:
        raise ValueError("manifest id must match its folder")
    # Older manifests predate this field and use bridge v1. Check again when
    # serving assets, so an incompatible panel cannot bypass discovery.
    api_version = data.get("apiVersion", 1)
    if type(api_version) is not int or api_version != API_VERSION:
        raise ValueError(f"unsupported apiVersion; this app supports {API_VERSION}")
    for key, limit in (("name", 80), ("version", 40), ("description", 240)):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError(f"invalid {key}")
    entry = data.get("entry", "index.html")
    if entry != "index.html" or (folder / entry).is_symlink() or not (folder / entry).is_file():
        raise ValueError("entry must be a regular index.html")
    return {**{key: data[key] for key in ("id", "name", "version", "description")},
            "apiVersion": api_version}


def list_extensions():
    base = root()
    if not base.exists():
        return {"extensions": [], "errors": [], "folder": str(base)}
    found, errors = [], []
    for folder in sorted(base.iterdir()):
        if folder.name.startswith(".") or not folder.is_dir():
            continue
        try:
            found.append(_manifest(folder))
        except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append({"folder": folder.name, "error": str(exc)})
    return {"extensions": found, "errors": errors, "folder": str(base)}


def asset(extension_id, name):
    """Return bytes and MIME; never follow symlinks or serve outside one valid folder."""
    if not ID.fullmatch(extension_id) or not ASSET.fullmatch(name) or name.startswith("."):
        raise FileNotFoundError("invalid extension path")
    folder = root() / extension_id
    _manifest(folder)
    file = folder / name
    if name == "manifest.json" or file.is_symlink() or not file.is_file():
        raise FileNotFoundError("extension asset not found")
    ctype = TYPES.get(file.suffix.lower())
    if not ctype or file.stat().st_size > 5 * 1024 * 1024:
        raise FileNotFoundError("unsupported extension asset")
    return file.read_bytes(), ctype
