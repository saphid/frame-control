"""The user's own itch.io account: an API key, the games it owns and their Android uploads.

Opt-in (store > sources > Connect itch.io). The key is kept in
frame_host.data_dir('itch-account.json') with mode 0600 and is only ever sent to
https://api.itch.io, in an Authorization header; _web drops it on any redirect
(downloads redirect to itch.io's storage host). It never goes into a URL, an error,
a log line or an API response. Owned-key listings stay in memory, never in the
disk cache. API: https://itch.io/docs/api/serverside. See docs/apk-repos.md.
"""
import hashlib, json, os, re, threading, time, urllib.error, urllib.parse

import frame_host
from . import SourceError, _web

API = 'https://api.itch.io'
HOSTS = ('api.itch.io',)
NAME = 'itch.io'
TTL = 600  # owned keys and uploads are re-read after ten minutes
PER_PAGE = 500  # the documented maximum for /profile/owned-keys
PAGES = 40  # stop after 20,000 owned keys
KEY = re.compile(r'[A-Za-z0-9_.-]{16,256}')
BAD_KEY = ('itch.io did not accept the API key. Create one in itch.io settings > '
           'API keys and connect again')
_lock = threading.Lock()
_cache = {}  # (key digest, what) -> (time, value)


class BadKey(SourceError):
    """itch.io refused the key: wrong, revoked or deleted."""


def path():
    return frame_host.data_dir('itch-account.json')


def _load():
    try:
        data = json.loads(path().read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get('key'), str) or not KEY.fullmatch(data['key']):
        return None
    return data


def status():
    """{'connected', 'username'}: what the page may know. Never the key; no network."""
    data = _load()
    return {'connected': bool(data), 'username': data.get('username') if data else None}


def connected():
    return _load() is not None


def _key():
    data = _load()
    if not data:
        raise SourceError('Connect your itch.io account first (store > sources > Connect itch.io)')
    return data['key']


def _save(key, username):
    target = path()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + '.tmp')
    try:
        os.remove(str(tmp))
    except FileNotFoundError:
        pass
    # Created 0600 (O_EXCL: never reuse a file someone else made), then moved into place.
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump({'key': key, 'username': username}, f)
        os.chmod(str(tmp), 0o600)
        os.replace(str(tmp), str(target))
    finally:
        if tmp.exists():
            tmp.unlink()


def _forget():
    with _lock:
        _cache.clear()


def _clean(message, key):
    return message.replace(key, '[API key]') if key else message


def _get(api_path, key, params=None):
    """JSON from api.itch.io; SourceError with a readable message (never the key) on failure."""
    url = API + api_path + ('?' + urllib.parse.urlencode(params) if params else '')
    wait = _web.wait_time(url)
    if wait:
        raise _web.limited_error(NAME, wait)
    try:
        with _web.open_url(url, HOSTS, {'Authorization': 'Bearer ' + key, 'Accept': 'application/json'}) as r:
            raw = r.read(8 * 1024 * 1024 + 1)
    except urllib.error.HTTPError as e:
        e.close()
        if e.code == 429:
            raise _web.limited_error(NAME, _web.throttle(url, e.headers)) from None
        if e.code in (401, 403):
            raise BadKey(BAD_KEY) from None
        raise SourceError('itch.io returned HTTP error %d; try again later' % e.code) from None
    except SourceError:
        raise
    except (OSError, ValueError) as e:
        reason = getattr(e, 'reason', None) or e
        raise SourceError(_clean('Could not reach itch.io: ' + str(reason), key)) from None
    if len(raw) > 8 * 1024 * 1024:
        raise SourceError('itch.io response is too large')
    try:
        data = json.loads(raw)
    except ValueError:
        raise SourceError('itch.io returned an invalid response') from None
    if not isinstance(data, dict):
        raise SourceError('itch.io returned an invalid response')
    errors = data.get('errors')
    if errors:  # documented: errors is an array of strings
        text = '; '.join(str(m) for m in errors if isinstance(m, (str, int)))[:200]
        if re.search(r'\b(invalid|revoked|expired)\b.*\bkey\b|\bkey\b.*\b(invalid|revoked|expired)\b', text, re.I) \
                and 'download key' not in text.lower():
            raise BadKey(BAD_KEY)
        raise SourceError(_clean('itch.io: ' + (text or 'request refused'), key))
    return data


def _cached(key, what, load):
    slot = (hashlib.sha256(key.encode()).hexdigest(), what)
    with _lock:
        hit = _cache.get(slot)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    value = load()
    with _lock:
        _cache[slot] = (time.time(), value)
    return value


def _use(call):
    """Run call(key); a key itch.io now refuses is removed, so the account shows disconnected."""
    key = _key()
    try:
        return call(key)
    except BadKey:
        if (_load() or {}).get('key') == key:  # not a key connected meanwhile
            disconnect()
        raise BadKey('itch.io no longer accepts the saved API key, so it was removed. '
                     'Create a new one in itch.io settings > API keys and connect again') from None


def connect(key):
    """Check key with itch.io (GET /profile), then save it. A refused key is never saved."""
    key = (key or '').strip() if isinstance(key, str) else ''
    if not KEY.fullmatch(key):
        raise BadKey('That does not look like an itch.io API key. Copy it from itch.io settings > API keys')
    user = _get('/profile', key).get('user')
    if not isinstance(user, dict):
        raise SourceError('itch.io returned an invalid profile')
    username = user.get('username') if isinstance(user.get('username'), str) else None
    _forget()
    _save(key, username)
    return {'message': 'Connected to itch.io' + (' as ' + username if username else ''), 'itch': status()}


def disconnect():
    _forget()
    try:
        os.remove(str(path()))
    except FileNotFoundError:
        pass
    return {'message': 'Disconnected from itch.io; the API key was deleted from this computer', 'itch': status()}


def owned_keys():
    """Every download key the account owns, newest first (GET /profile/owned-keys, all pages)."""
    def load(key):
        keys = []
        for page in range(1, PAGES + 1):
            batch = _get('/profile/owned-keys', key, {'page': page, 'per_page': PER_PAGE}).get('owned_keys')
            # Documented: a page can hold fewer than per_page even when more follow; an empty one ends it.
            if not batch or not isinstance(batch, list):
                break
            keys.extend(k for k in batch if isinstance(k, dict))
        return keys
    return _use(lambda key: _cached(key, 'owned', lambda: load(key)))


def _number(value):
    return value if type(value) is int and value > 0 else None


def is_android(upload):
    """An upload marked for Android, or an .apk file. The marker's field name is not in the
    public reference: itch.io's traits use p_<platform> (p_windows...), so p_android is assumed."""
    traits = upload.get('traits') if isinstance(upload.get('traits'), list) else []
    platforms = upload.get('platforms') if isinstance(upload.get('platforms'), dict) else {}
    filename = str(upload.get('filename') or '').lower()
    return 'p_android' in traits or upload.get('p_android') is True or 'android' in platforms \
        or filename.endswith('.apk')


def android_uploads(uploads):
    """Installable Android uploads, best first: .apk files, then full games, then newest."""
    chosen = []
    for u in uploads if isinstance(uploads, list) else []:
        if not isinstance(u, dict) or not _number(u.get('id')) or not is_android(u):
            continue
        traits = u.get('traits') if isinstance(u.get('traits'), list) else []
        if u.get('type') not in (None, 'default') or u.get('preorder') is True or 'preorder' in traits:
            continue  # soundtracks, books, placeholders
        if u.get('storage') == 'external':
            continue  # hosted on another site: not something itch.io can hand us
        chosen.append(u)
    chosen.sort(key=lambda u: str(u.get('updated_at') or u.get('created_at') or ''), reverse=True)
    chosen.sort(key=lambda u: (not str(u.get('filename') or '').lower().endswith('.apk'),
                               u.get('demo') is True or 'demo' in (u.get('traits') or [])))
    return chosen


def uploads(game_id, download_key_id):
    """The game's uploads this download key may fetch (GET /games/ID/uploads)."""
    game_id, download_key_id = _number(game_id), _number(download_key_id)
    if not game_id or not download_key_id:
        raise SourceError('Invalid itch.io game')
    return _use(lambda key: _cached(key, ('uploads', game_id, download_key_id), lambda: _get(
        '/games/%d/uploads' % game_id, key, {'download_key_id': download_key_id}).get('uploads') or []))


def download_url(upload_id, download_key_id):
    upload_id, download_key_id = _number(upload_id), _number(download_key_id)
    if not upload_id or not download_key_id:
        raise SourceError('Invalid itch.io upload')
    return API + '/uploads/%d/download?' % upload_id + urllib.parse.urlencode({'download_key_id': download_key_id})


def download(upload_id, download_key_id):
    """The APK, through _web.apk: the key goes to api.itch.io only, never to the storage host."""
    url = download_url(upload_id, download_key_id)
    return _use(lambda key: _web.apk(url, HOSTS, None, name=NAME,
                                     headers={'Authorization': 'Bearer ' + key}, redirects=_web.ANY))
