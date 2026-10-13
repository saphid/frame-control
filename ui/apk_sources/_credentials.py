"""Logins for sources behind one: HTTP basic auth and access tokens.

Saved apart from the source settings, in frame_host.data_dir('source-credentials.json')
(mode 0600), keyed by a caller-chosen name: an F-Droid source id, 'github'. Each
credential belongs to one exact origin (https, host, port) and is only ever sent
to a request for that origin: Handler adds it to each request, redirects
included, and removes any Authorization header from every other request.

Artwork (for_url, and Handler(..., scoped=True)) is stricter: the URL must also be
under the credential's scope by whole path segments, with no dot segments, encoded
slashes or ';' a server could normalise into a path outside it.

Secrets leave this module only as an Authorization header value. Credential's
repr hides them, and nothing here puts them in an exception message.

Each change is a read-modify-write under an inter-process lock (the CLI and the
app may both save), so one process can't undo another's save or removal.
"""
import base64
import contextlib
import errno
import json
import os
import tempfile
import threading
import urllib.parse
import urllib.request

import frame_host

_lock = threading.RLock()
MAX = 4096  # longest username, password or token accepted


def _path():
    return frame_host.data_dir('source-credentials.json')


@contextlib.contextmanager
def _changing():
    """This thread, then this process, holds the credentials file for a read-modify-write."""
    path = _path().with_name('source-credentials.lock')
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(path), 'a+b') as f:
            if os.name == 'nt':
                import msvcrt
                while True:
                    try:
                        f.seek(0)
                        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
                        break
                    except OSError as e:  # LK_LOCK gives up after ~10 s of contention; keep waiting
                        if e.errno not in (errno.EACCES, errno.EDEADLK):
                            raise
                try:
                    yield
                finally:
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _segments(path):
    """A URL path's decoded segments, or None if a server might read it as another path:
    '.' or '..' (plain or percent-encoded), encoded '/' or '\\', '%' left after decoding
    (double encoding), or ';' path parameters."""
    if ';' in path or '\\' in path:
        return None
    parts = [urllib.parse.unquote(part) for part in path.split('/')]
    if any(part in ('.', '..') or '/' in part or '\\' in part or '%' in part or ';' in part for part in parts):
        return None
    return parts


def in_scope(credential, url):
    """True if url is on credential's origin and under its scope by whole, plain path segments."""
    if credential is None or not credential.matches(url):
        return False
    try:
        path, scope = urllib.parse.urlsplit(url).path, urllib.parse.urlsplit(credential.scope).path
    except ValueError:
        return False
    parts, base = _segments(path), _segments(scope)
    if parts is None or base is None:
        return False
    if base and base[-1] == '':
        base = base[:-1]  # 'https://h/repo/' covers '/repo/x', not '/repository'
    return parts[:len(base)] == base


def origin(url):
    """'https://host:port' for an https URL; ValueError for anything else."""
    p = urllib.parse.urlsplit(url)
    port = p.port  # raises ValueError on a bad port
    if p.scheme.lower() != 'https' or not p.hostname:
        raise ValueError('credentials are only sent over HTTPS')
    host = p.hostname.lower()
    return 'https://%s:%d' % ('[%s]' % host if ':' in host else host, port or 443)


def _check(value, what, allow_empty=False):
    if not isinstance(value, str) or (not value and not allow_empty) or len(value) > MAX:
        raise ValueError('invalid ' + what)
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError(what + ' must not contain control characters')
    return value


class Credential:
    """A username and password (basic) or a token (bearer) for one origin.

    scope is a URL prefix used only to pick a stored credential for a URL (for_url);
    whether a request gets the credential depends on its origin alone."""
    __slots__ = ('origin', 'scope', 'username', '_secret')

    def __init__(self, scope, secret, username=None):
        self.origin = origin(scope)
        self.scope = scope
        if username is not None:
            _check(username, 'username')
            if ':' in username:
                raise ValueError('username must not contain ":"')
            _check(secret, 'password', allow_empty=True)
        else:
            _check(secret, 'token')
            if any(c.isspace() for c in secret):
                raise ValueError('token must not contain spaces')
        self.username, self._secret = username, secret

    @property
    def kind(self):
        return 'bearer' if self.username is None else 'basic'

    def header(self):
        if self.username is None:
            return 'Bearer ' + self._secret
        return 'Basic ' + base64.b64encode((self.username + ':' + self._secret).encode('utf-8')).decode('ascii')

    def matches(self, url):
        """True only for a URL on exactly this credential's origin."""
        try:
            return origin(url) == self.origin
        except ValueError:
            return False

    def same(self, other):
        return isinstance(other, Credential) and (self.origin, self.username, self._secret) == (
            other.origin, other.username, other._secret)

    def __repr__(self):
        return '<Credential %s for %s>' % (self.kind, self.origin)

    def _json(self):
        return {'scope': self.scope, 'username': self.username, 'secret': self._secret}


def basic(scope, username, password):
    """Basic auth for scope's origin, e.g. basic('https://example.org/fdroid/repo/', 'me', 'pw')."""
    return Credential(scope, password, username)


def bearer(scope, token):
    """An access token for scope's origin, sent as 'Authorization: Bearer <token>'."""
    return Credential(scope, token)


def _read():
    try:
        with open(str(_path()), encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError
        return data
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        return {}  # unreadable: as if none were saved; the next save rewrites it


def _save(data):
    path = _path()
    if not data:
        try:
            os.remove(str(path))
        except FileNotFoundError:
            pass
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix='.credentials-', suffix='.part')  # created 0600
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, separators=(',', ':'))
        os.chmod(tmp, 0o600)
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def get(key):
    """The saved Credential for key, or None."""
    with _lock:
        item = _read().get(key)
    try:
        return Credential(item['scope'], item['secret'], item.get('username'))
    except (TypeError, KeyError, ValueError):
        return None


def has(key):
    return get(key) is not None


def put(key, credential):
    if not isinstance(credential, Credential):
        raise TypeError('put() needs a Credential')
    with _changing():
        data = _read()
        data[key] = credential._json()
        _save(data)


def remove(key):
    """Delete key's credential from disk; True if there was one."""
    with _changing():
        data = _read()
        if key not in data:
            return False
        del data[key]
        _save(data)
        return True


def for_url(url):
    """A saved credential url is in the scope of (see in_scope), or None. Call it again for
    each redirect hop: the answer depends only on the URL being requested."""
    with _lock:
        keys = list(_read())
    for key in keys:
        credential = get(key)
        if in_scope(credential, url):
            return credential
    return None


class Handler(urllib.request.BaseHandler):
    """Adds the credential to requests for its origin (redirects included) and strips
    Authorization from every other request, so a redirect elsewhere never gets it.
    scoped=True also requires each request, redirects included, to be in_scope."""
    handler_order = 900  # after the default processors

    def __init__(self, credential, scoped=False):
        self.credential, self.scoped = credential, scoped

    def _request(self, req):
        req.remove_header('Authorization')
        allowed = in_scope if self.scoped else lambda c, url: c is not None and c.matches(url)
        if allowed(self.credential, req.full_url):
            req.add_unredirected_header('Authorization', self.credential.header())
        return req

    http_request = https_request = _request
