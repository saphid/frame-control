"""Preserve prior movie overrides for the pinned Animation Changer backend.

Only the three published video names are writable. Empty selections leave
unmanaged overrides alone; clearing an owned selection restores its original.
"""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import stat
import uuid

VIDEOS = ('deck_startup.webm', 'steam_os_suspend.webm',
          'steam_os_suspend_from_throbber.webm')


def identity(path):
    info = path.lstat()
    return [info.st_dev, info.st_ino]


class Overrides:
    def __init__(self, movies):
        self.movies = Path(movies).resolve()
        self.root = self.movies/'.frame-control-animation-backups'

    @contextmanager
    def locked(self):
        self.root.mkdir(mode=0o700, exist_ok=True)
        if self.root.is_symlink() or not self.root.is_dir():
            raise RuntimeError('Animation backup directory must be a real directory')
        descriptor = os.open(self.root/'lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'a+b') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def paths(self, video):
        if video not in VIDEOS:
            raise ValueError('Unknown animation override name')
        entry = self.root/video
        if entry.is_symlink():
            raise RuntimeError('Animation backup entry must not be a symlink')
        return self.movies/video, entry, entry/'owner.json', entry/'original'

    def read(self, target, marker):
        if not os.path.lexists(marker):
            return None
        descriptor = os.open(marker, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor) as source:
            record = json.load(source)
        if (not isinstance(record, dict) or set(record) != {'schema', 'target', 'link', 'identity', 'original'}
                or record['schema'] != 1 or record['target'] != str(target)
                or not isinstance(record['link'], str) or not os.path.isabs(record['link'])
                or type(record['original']) is not bool
                or not isinstance(record['identity'], list) or len(record['identity']) != 2
                or not all(type(v) is int for v in record['identity'])):
            raise RuntimeError('Invalid animation ownership record; keeping override and backup')
        return record

    @staticmethod
    def verify(target, record, backup):
        if (not target.is_symlink() or os.readlink(target) != record['link']
                or identity(target) != record['identity']):
            raise RuntimeError('Animation override changed outside Frame Control; keeping override and backup')
        if os.path.lexists(backup) != record['original']:
            raise RuntimeError('Animation backup is missing or unexpected; keeping override')
        if record['original'] and not (backup.is_symlink() or backup.is_file()):
            raise RuntimeError('Animation backup is not a file or symlink; keeping override')

    @staticmethod
    def write(marker, record):
        temporary = marker.with_name('owner-'+uuid.uuid4().hex+'.tmp')
        try:
            with temporary.open('x') as dest:
                json.dump(record, dest)
                dest.flush()
                os.fsync(dest.fileno())
            os.replace(temporary, marker)
        finally:
            if temporary.exists():
                temporary.unlink()

    def apply(self, video, source):
        target, entry, marker, backup = self.paths(video)
        if source is None and not os.path.lexists(self.root):
            return  # Default startup must not create state or touch Steam files.
        if source is not None:
            source = Path(source).resolve(strict=True)
            if not source.is_file() or source == target:
                raise ValueError('Selected animation is missing or refers to its own override')
        with self.locked():
            record = self.read(target, marker)
            if source is None:
                if record is None:
                    return  # An empty selection does not own an existing movie.
                self.verify(target, record, backup)
                if record['original']:
                    os.replace(backup, target)
                else:
                    target.unlink()
                marker.unlink()
                entry.rmdir()
                return
            if record is not None:
                self.verify(target, record, backup)
            elif os.path.lexists(backup):
                raise RuntimeError('Unclaimed animation backup exists; keeping both files')
            elif os.path.lexists(target) and not (target.is_symlink() or stat.S_ISREG(target.lstat().st_mode)):
                raise RuntimeError('Animation override is not a file or symlink')
            entry.mkdir(mode=0o700, exist_ok=True)
            temporary = entry/('link-'+uuid.uuid4().hex)
            os.symlink(source, temporary)
            original = record['original'] if record else os.path.lexists(target)
            prior = entry/('prior-'+uuid.uuid4().hex)
            replaced = False
            saved = False
            committed = False
            try:
                if record is not None:
                    os.rename(target, prior)
                    saved = True
                elif original:
                    os.rename(target, backup)
                    saved = True
                os.replace(temporary, target)
                replaced = True
                new = dict(schema=1, target=str(target), link=str(source),
                           identity=identity(target), original=original)
                self.write(marker, new)
                committed = True
            except BaseException:
                if replaced:
                    if record:
                        os.replace(prior, target)
                    elif saved:
                        os.replace(backup, target)
                    else:
                        target.unlink()
                elif saved:
                    os.rename(prior if record else backup, target)
                raise
            finally:
                if os.path.lexists(temporary):
                    temporary.unlink()
                if committed and os.path.lexists(prior):
                    prior.unlink()


def install(namespace):
    store = Overrides(namespace['OVERRIDE_PATH'])

    def apply(video, anim_id):
        if anim_id == '':
            return store.apply(video, None)
        source = None
        for animation in namespace['config']['downloads']:
            if animation['id'] == anim_id:
                source = str(Path(namespace['DOWNLOADS_PATH'])/(anim_id+'.webm'))
                break
        else:
            for animation in namespace['config']['custom_animations']:
                if animation['id'] == anim_id:
                    source = animation['path']
                    break
            else:
                for animation in namespace['local_animations']:
                    if animation['id'] == anim_id:
                        source = str(Path(namespace['ANIMATIONS_PATH'])/anim_id)
                        break
        if source is None:
            raise ValueError('Selected animation was not found; keeping current override')
        return store.apply(video, source)

    namespace['apply_animation'] = apply
