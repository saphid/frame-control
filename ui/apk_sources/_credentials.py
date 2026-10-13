"""Logins for sources behind one: HTTP basic auth and access tokens.

Saved apart from the source settings, in frame_host.data_dir('source-credentials.json')
(mode 0600), keyed by a caller-chosen name: an F-Droid source id, 'github'. Each
credential belongs to one exact origin (https, host, port) and is only ever sent
to a request for that origin: Handler adds it to each request, redirects
included, and removes any Authorization header from every other request.

Secrets leave this module only as an Authorization header value. Credential's
repr hides them, and nothing here puts them in an exception message.
"""
import base64
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
    with _lock:
        data = _read()
        data[key] = credential._json()
        _save(data)


def remove(key):
    """Delete key's credential from disk; True if there was one."""
    with _lock:
        data = _read()
        if key not in data:
            return False
        del data[key]
        _save(data)
        return True


def for_url(url):
    """A saved credential whose origin matches url and whose scope url is under, or None."""
    with _lock:
        keys = list(_read())
    for key in keys:
        credential = get(key)
        if credential and credential.matches(url) and url.startswith(credential.scope):
            return credential
    return None


class Handler(urllib.request.BaseHandler):
    """Adds the credential to requests for its origin (redirects included) and strips
    Authorization from every other request, so a redirect elsewhere never gets it."""
    handler_order = 900  # after the default processors

    def __init__(self, credential):
        self.credential = credential

    def _request(self, req):
        req.remove_header('Authorization')
        if self.credential is not None and self.credential.matches(req.full_url):
            req.add_unredirected_header('Authorization', self.credential.header())
        return req

    http_request = https_request = _request
