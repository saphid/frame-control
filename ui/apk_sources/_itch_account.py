"""The user's own itch.io account: an API key, the games it owns and their Android uploads.

Opt-in (store > sources > Connect itch.io). The key is kept in
frame_host.data_dir('itch-account.json') with mode 0600 and is only ever sent to
https://api.itch.io, in an Authorization header. Downloads end on itch.io's storage
host, fetched without the key from a checked public address (_web.public_apk).
The key never goes into a URL, an error, a log line or an API response. Owned-key
listings stay in memory, never in the disk cache.
API: https://itch.io/docs/api/serverside. See docs/apk-repos.md.
"""
import hashlib, http.client, json, os, re, tempfile, threading, time, urllib.error, urllib.parse, urllib.request, zipfile

import frame_host
from . import SourceError, SourceLimited, _web

API = 'https://api.itch.io'
HOSTS = ('api.itch.io',)
NAME = 'itch.io'
TTL = 600  # owned keys and uploads are re-read after ten minutes
PER_PAGE = 500  # the documented maximum for /profile/owned-keys
PAGES = 40  # stop after 20,000 owned keys
KEY = re.compile(r'[A-Za-z0-9_.-]{16,256}')
BAD_KEY = ('itch.io did not accept the API key. Create one in itch.io settings > '
           'API keys and connect again')
REVOKED = ('itch.io no longer accepts the saved API key, so it was removed. '
           'Create a new one in itch.io settings > API keys and connect again')
REDIRECTS = (301, 302, 303, 307, 308)
# Everything a connection or response can raise. http.client's errors (IncompleteRead,
# BadStatusLine...) are not OSErrors, and BadStatusLine repeats what the server sent.
NETWORK = (OSError, ValueError, http.client.HTTPException)
_lock = threading.Lock()  # the cache
_cache = {}  # (generation, key digest, what) -> (time, value)
_account = threading.Lock()  # saving and deleting the key file
_generation = [0]  # bumped by every save and delete: a connect that started earlier doesn't save


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
    """Write the key file through a fresh 0600 temporary file (mkstemp), then move it into place."""
    target = path()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix='.itch-account-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as f:
            os.chmod(tmp, 0o600)  # mkstemp already does on POSIX; say so for every platform
            json.dump({'key': key, 'username': username}, f)
        os.replace(tmp, str(target))
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _forget():
    with _lock:
        _cache.clear()


def _clean(message, key):
    """message without the key, or any start of it (8+ characters, as truncation leaves), in
    any letter case, with any of its characters written literally or percent-encoded (%4B or
    %4b). The only redaction used here: every message that might hold the key goes through it.
    (The key's characters are letters, digits and _.-, so +/space encoding can't change it.)"""
    if not key:
        return message
    # Each character: itself, or the percent-encoding of either of its letter cases.
    tokens = ['(?:%s)' % '|'.join([re.escape(c)] + ['%%%02x' % ord(v) for v in sorted({c.lower(), c.upper()})])
              for c in key]
    start, rest = re.compile(''.join(tokens[:8]), re.I), [re.compile(t, re.I) for t in tokens[8:]]
    out, pos = [], 0
    while True:
        found = start.search(message, pos)
        if not found:
            break
        end = found.end()
        for token in rest:  # as much more of the key as follows
            more = token.match(message, end)
            if not more:
                break
            end = more.end()
        out += [message[pos:found.start()], '[API key]']
        pos = end
    return ''.join(out) + message[pos:]


class _Stay(urllib.request.HTTPRedirectHandler):
    """Don't follow: the caller decides where a redirect may go, and never sends the key there."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open(url, key, accept='application/json'):
    """GET url on api.itch.io with the key. Redirects come back as HTTPError 30x."""
    _web.checked_url(url, HOSTS)
    wait = _web.wait_time(url)
    if wait:
        raise _web.limited_error(NAME, wait)
    return urllib.request.build_opener(_Stay()).open(urllib.request.Request(
        url, headers={'User-Agent': _web.UA, 'Authorization': 'Bearer ' + key, 'Accept': accept}), timeout=60)


def _refused(code, key, api_path, message=None):
    """A refusal that may be about the key (401/403, or an "invalid key" error): BadKey only
    once /profile confirms the key itself is refused; otherwise it's this request (a game or
    upload this purchase doesn't cover), and the key stays."""
    if api_path != '/profile':
        _get('/profile', key)  # raises BadKey if the key is the problem
        raise SourceError(message or 'itch.io refused this request (HTTP %d); your purchase may not include it' % code)
    raise BadKey(BAD_KEY)


def _network_error(e, key):
    reason = getattr(e, 'reason', None) or e
    return SourceError(_clean('Could not reach itch.io: ' + str(reason), key))


BAD_KEY_TEXT = re.compile(r'\b(invalid|revoked|expired)\b.*\bkey\b|\bkey\b.*\b(invalid|revoked|expired)\b', re.I)


def _checked(raw, key, api_path):
    """Decoded JSON object from api.itch.io, or SourceError/BadKey from its errors array."""
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
        messages = [str(m) for m in errors if isinstance(m, (str, int))]
        # Judged on itch.io's own words: redacted text says "[API key]", which would look like a key error.
        about_key = any(BAD_KEY_TEXT.search(m) and 'download key' not in m.lower() for m in messages)
        # Each message loses the key before joining and shortening, so no part of it survives the cut.
        text = _clean('; '.join(_clean(m, key) for m in messages)[:200], key)
        if about_key:
            _refused(None, key, api_path, 'itch.io: ' + text)
        raise SourceError('itch.io: ' + (text or 'request refused'))
    return data


def _get(api_path, key, params=None):
    """JSON from api.itch.io; SourceError with a readable message (never the key) on failure."""
    url = API + api_path + ('?' + urllib.parse.urlencode(params) if params else '')
    try:
        with _open(url, key) as r:
            raw = r.read(8 * 1024 * 1024 + 1)
    except urllib.error.HTTPError as e:
        e.close()
        if e.code == 429:
            raise _web.limited_error(NAME, _web.throttle(url, e.headers)) from None
        if e.code in (401, 403):
            _refused(e.code, key, api_path)
        raise SourceError('itch.io returned HTTP error %d; try again later' % e.code) from None
    except SourceError:
        raise
    except NETWORK as e:
        raise _network_error(e, key) from None
    return _checked(raw, key, api_path)


def _cached(key, what, load):
    slot = (_generation[0], hashlib.sha256(key.encode()).hexdigest(), what)
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
    with _account:  # the key and the connection it belongs to, read together
        key, generation = _key(), _generation[0]
    try:
        return call(key)
    except BadKey:
        with _account:
            # Only the connection this call started with: a reconnect meanwhile (even with
            # the same key) has been checked since, and is not undone by this older verdict.
            if _generation[0] == generation and (_load() or {}).get('key') == key:
                _delete()
        raise BadKey(REVOKED) from None


def connect(key):
    """Check key with itch.io (GET /profile), then save it. A refused key is never saved, and
    nor is one whose check finished after a disconnect or another connect."""
    key = (key or '').strip() if isinstance(key, str) else ''
    if not KEY.fullmatch(key):
        raise BadKey('That does not look like an itch.io API key. Copy it from itch.io settings > API keys')
    with _account:
        started = _generation[0]
    user = _get('/profile', key).get('user')  # the network, outside the lock
    if not isinstance(user, dict):
        raise SourceError('itch.io returned an invalid profile')
    username = user.get('username') if isinstance(user.get('username'), str) else None
    with _account:
        if _generation[0] != started:
            raise SourceError('The itch.io connection changed while the key was being checked; '
                              'nothing was saved. Try again')
        _generation[0] += 1
        _save(key, username)
    _forget()
    return {'message': 'Connected to itch.io' + (' as ' + username if username else ''), 'itch': status()}


def _delete():
    """Remove the key file; call with _account held."""
    _generation[0] += 1
    try:
        os.remove(str(path()))
    except FileNotFoundError:
        pass
    _forget()


def disconnect():
    with _account:
        _delete()
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


def _fetch(url, key):
    """Ask api.itch.io for the file. Not checked against a live account, so this accepts each
    plausible answer: a redirect to storage, JSON naming the storage URL, or the file itself."""
    try:
        r = _open(url, key, 'application/vnd.android.package-archive, application/json;q=0.5, */*;q=0.1')
    except urllib.error.HTTPError as e:
        e.close()
        if e.code in REDIRECTS:
            target = e.headers.get('Location')
        elif e.code == 429:
            raise _web.limited_error(NAME, _web.throttle(url, e.headers)) from None
        elif e.code in (401, 403):
            _refused(e.code, key, '/uploads')
        else:
            raise SourceError('itch.io returned HTTP error %d for the download; try again later' % e.code) from None
    except SourceError:
        raise
    except NETWORK as e:
        raise _network_error(e, key) from None
    else:
        with r:
            if 'json' not in (r.headers.get('Content-Type') or '').lower():
                try:
                    return _web.save_apk(r)  # served by api.itch.io itself
                except NETWORK + (zipfile.BadZipFile,) as e:
                    raise SourceError(_clean('Could not download APK: ' + str(e), key)) from None
            try:
                raw = r.read(1024 * 1024 + 1)
            except NETWORK as e:
                raise _network_error(e, key) from None
        target = _checked(raw, key, '/uploads').get('url')
    if not isinstance(target, str) or not target:
        raise SourceError('itch.io did not say where to download the file')
    def refuse(hop):  # on the first URL and on every redirect after it, before any lookup
        if _carries_key(hop, key):
            raise SourceError('itch.io pointed the download at a URL carrying your API key; refused, '
                              'so the key is not sent to the storage server')
    try:
        return _web.public_apk(urllib.parse.urljoin(url, target), NAME, check=refuse)  # no key sent
    except SourceLimited as e:
        raise SourceLimited(_clean(str(e), key), e.retry_after) from None
    except SourceError as e:
        raise type(e)(_clean(str(e), key)) from None


def _carries_key(url, key):
    """True if url holds the key (or 8+ characters of its start), however cased or encoded, or
    an itch.io API-key parameter: go-itchio puts the key in ?api_key=, and storage must never
    get it. Other parameters (signatures, tokens) are the storage URL's own and are kept."""
    for form in (url, urllib.parse.unquote(url), urllib.parse.unquote_plus(url)):
        if _clean(form, key) != form:
            return True
    names = {name.lower() for name, _ in urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query,
                                                                  keep_blank_values=True)}
    return bool(names & {'api_key', 'apikey', 'api-key'})


def download(upload_id, download_key_id):
    """The APK: the key goes to api.itch.io only, never to the storage host."""
    url = download_url(upload_id, download_key_id)
    return _use(lambda key: _fetch(url, key))
