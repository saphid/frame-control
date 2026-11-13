"""Confined screenshot copies for the exact managed Shotty 0.1.0 archive."""
from contextlib import contextmanager
import os
from pathlib import Path
import secrets
import stat

MAX_IMAGE = 64 * 1024 * 1024
MAX_FILES = 10000


def app_id(value):
    if type(value) is not int or not 0 <= value <= 18446744073709551615:
        raise ValueError('Choose a numeric Steam screenshot app ID')
    return value


def filename(value):
    if (not isinstance(value, str) or not value or value in ('.', '..') or
            any(c in value for c in '/\\\x00') or any(ord(c) < 32 for c in value) or
            len(value.encode('utf-8')) > 255):
        raise ValueError('Invalid screenshot filename')
    return value


def destination(root, name, leaf):
    if Path(root) != Path.home()/'Pictures/Screenshots':
        raise ValueError('Screenshot output must stay in Pictures/Screenshots')
    label = ''.join(' ' if c in '/\\:' or ord(c) < 32 else c for c in str(name))
    label = label.strip(' .').encode('utf-8')[:200].decode('utf-8', errors='ignore') or 'Unknown'
    return Path(root)/label/filename(leaf)


@contextmanager
def parent(path, create=False):
    parts = Path(path).relative_to(Path.home()).parts
    if not parts or any(p in ('', '.', '..') for p in parts):
        raise ValueError('Screenshot path escapes the user home')
    fd = os.open(Path.home(), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            if create:
                try: os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError: pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd, filename(parts[-1])
    finally:
        os.close(fd)


def _read(fd):
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > MAX_IMAGE:
        raise ValueError('Screenshot must be an owned regular image within the size limit')
    with os.fdopen(os.dup(fd), 'rb') as stream:
        data = stream.read(MAX_IMAGE+1)
    after = os.fstat(fd)
    if len(data) > MAX_IMAGE or (info.st_size, info.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Screenshot changed while copying')
    return data


def read_source(source):
    source = Path(source)
    if source == Path('/tmp/gamescope.raw_encoded.png'):
        fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try: return _read(fd)
        finally: os.close(fd)
    parts = source.relative_to(Path.home()).parts
    if (len(parts) != 10 or parts[:4] != ('.local', 'share', 'Steam', 'userdata') or
            not parts[4].isascii() or not parts[4].isdigit() or parts[5:7] != ('760', 'remote') or
            not parts[7].isascii() or not parts[7].isdigit() or parts[8] != 'screenshots'):
        raise ValueError('Source must be a Steam userdata screenshot')
    with parent(source) as (directory, leaf):
        fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        try: return _read(fd)
        finally: os.close(fd)


def sources(app=None, leaf=None):
    if app is not None: app_id(app)
    if leaf is not None: filename(leaf)
    root = Path.home()/'.local/share/Steam/userdata'
    pattern = '[0-9]*/760/remote/'+(str(app) if app is not None else '[0-9]*')+'/screenshots/'
    pattern += '*' if leaf is not None else '*.jpg'
    found = []
    for index, path in enumerate(root.glob(pattern)):
        if index >= MAX_FILES: raise ValueError('Too many Steam screenshots for one copy operation')
        if leaf is not None and path.name != leaf: continue
        found.append(path)
    return found


def copy_file(source, target, replace=False):
    """Copy through held directory descriptors; never hardlink the original image."""
    return write_image(read_source(source), target, replace)


def write_image(data, target, replace=False):
    target = Path(target)
    parts = target.relative_to(Path.home()).parts
    if parts[:2] != ('Pictures', 'Screenshots') or len(parts) not in (3, 4):
        raise ValueError('Screenshot output escapes Pictures/Screenshots')
    with parent(target, create=True) as (directory, leaf):
        try:
            existing = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        except FileNotFoundError: pass
        else:
            try:
                previous = _read(existing)
                if previous == data: return False
                if not replace: raise FileExistsError('A different screenshot already exists')
            finally: os.close(existing)
        temporary = '.framey-shotty-'+secrets.token_hex(12)
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        try:
            with os.fdopen(fd, 'wb') as stream: stream.write(data)
            if replace:
                os.replace(temporary, leaf, src_dir_fd=directory, dst_dir_fd=directory)
            else:
                # Both names are on the destination filesystem. Publication is
                # exclusive, while the source may live on a different device.
                os.link(temporary, leaf, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
            return True
        finally:
            try: os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError: pass
