"""Curated publisher releases; optional topic discovery is page-only."""
import fnmatch, hashlib, json, os, re, sys, threading, urllib.parse

from . import SourceAuthError, SourceError, _credentials, _web

KIND = 'github'
API = 'https://api.github.com'
ENV = 'FRAME_GITHUB_TOKEN'  # wins over a token saved in source settings
CREDENTIAL = 'github'  # _credentials key; only ever sent to api.github.com
_rejected = set()  # SHA-256 of tokens GitHub answered 401 to (this run only)
_rejected_lock = threading.Lock()
TOPICS = ('oculus-quest', 'openxr', 'quest')
HOSTS = ('github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com')


def sources():
    return [{'id': KIND, 'kind': KIND, 'name': 'GitHub releases', 'url': 'https://github.com',
             'builtin': True, 'enabled': True, 'trust': 'community', 'token': token_status()}]


def _token():
    """(token, where it came from) or (None, None). The environment variable wins."""
    env = os.environ.get(ENV)
    if env:
        return env, 'env'
    saved = _credentials.get(CREDENTIAL)
    if saved and saved.kind == 'bearer':
        return saved, 'saved'
    return None, None


def _credential(token):
    if isinstance(token, _credentials.Credential):
        return token
    try:
        return _credentials.bearer(API + '/', token)
    except ValueError as e:
        raise SourceError('%s is not a usable GitHub token: %s' % (ENV, e)) from None


def _digest(credential):
    return hashlib.sha256(credential.header().encode()).hexdigest()


def token_status():
    """Whether a token is set, where from, and whether GitHub rejected it; never the token."""
    token, where = _token()
    rejected = False
    if token is not None:
        try:
            with _rejected_lock:
                rejected = _digest(_credential(token)) in _rejected
        except SourceError:
            rejected = True
    return {'set': token is not None, 'from': where, 'rejected': rejected}


def set_token(token):
    """Save a personal access token for api.github.com (FRAME_GITHUB_TOKEN still wins)."""
    if not isinstance(token, str) or not token.strip():
        raise SourceError('Paste a GitHub token')
    try:
        credential = _credentials.bearer(API + '/', token.strip())
    except ValueError as e:
        raise SourceError('That is not a usable GitHub token: ' + str(e)) from None
    _credentials.put(CREDENTIAL, credential)
    with _rejected_lock:
        _rejected.discard(_digest(credential))  # a fresh chance
    return {'message': 'GitHub token saved' + (' (%s is set and is used instead)' % ENV if os.environ.get(ENV) else '')}


def clear_token():
    _credentials.remove(CREDENTIAL)
    return {'message': 'GitHub token removed'}


def _curated():
    with open(os.path.join(os.path.dirname(__file__), 'github_curated.json')) as f:
        return json.load(f)


def _api(path):
    """GET from the GitHub API, with the user's token if there is one. If GitHub rejects
    the token (401), retry once without it, like Obtainium, and remember the rejection."""
    headers = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
    token, _ = _token()
    auth = _credential(token) if token is not None else None
    with _rejected_lock:
        if auth and _digest(auth) in _rejected:
            auth = None  # already refused this run: don't spend a request on it again
    hint = ' (add a GitHub token in the store\'s source settings, or set %s, to raise the limit)' % ENV
    if token is not None and not auth:
        hint = ' (GitHub rejected your token; replace it in the store\'s source settings)'

    def get(auth):
        return _web.read(API + path, ('api.github.com',), headers, name='GitHub',
                         hint='' if auth else hint, auth=auth)
    try:
        try:
            data = get(auth)
        except SourceAuthError:
            if not auth:
                raise
            with _rejected_lock:
                _rejected.add(_digest(auth))
            print('GitHub rejected the access token (HTTP 401); continuing without it', file=sys.stderr)
            hint = ' (GitHub rejected your token; replace it in the store\'s source settings)'
            data = get(None)
        return json.loads(data)
    except (ValueError, TypeError) as e:
        raise SourceError('Invalid GitHub response') from e


def _entry(source, c, approved=True):
    artwork = c.get('images') or {}
    icon = artwork.get('icon') or c.get('icon') or 'https://github.com/' + c['repo'].split('/')[0] + '.png'
    images = {'icon': icon,
              # No GitHub social-preview card: it's repo text and stats, not art; the UI draws a fallback.
              'banner': artwork.get('banner'),
              'screenshots': list(artwork.get('screenshots') or [])}
    return {'source': source['id'], 'id': c['repo'], 'package': None,
            'name': c['name'], 'summary': c.get('summary') or '', 'icon': icon,
            'images': images,
            'page': 'https://github.com/' + c['repo'], 'version': None, 'version_code': None,
            'min_sdk': None, 'abis': None, 'vr': c.get('vr'), 'size': None,
            'free': True if approved else None, 'license': c.get('license'), 'updated': None,
            'downloadable': approved}


def search(source, query, limit=50):
    limit = max(0, min(int(limit), 100))
    if not limit:
        return []
    if query.startswith('topic:'):
        topic = query[6:].strip()
        if topic not in TOPICS:
            raise SourceError('Choose topic:oculus-quest, topic:openxr or topic:quest')
        data = _api('/search/repositories?' + urllib.parse.urlencode(
            {'q': 'topic:' + topic + ' archived:false', 'sort': 'stars', 'per_page': limit}))
        curated = {c['repo'].lower(): c for c in _curated()}
        out = []
        for repo in data.get('items', []):
            c = curated.get(repo['full_name'].lower())
            entry = _entry(source, c or {'repo': repo['full_name'], 'name': repo['name'],
                           'summary': repo.get('description'), 'vr': True,
                           'icon': (repo.get('owner') or {}).get('avatar_url')}, bool(c))
            out.append(entry)
        return out
    words = query.lower().split()
    return [_entry(source, c) for c in _curated()
            if all(w in (c['name'] + ' ' + c['repo'] + ' ' + c['summary']).lower()
                   for w in words)][:limit]


def details(source, entry_id):
    c = next((c for c in _curated() if c['repo'].lower() == entry_id.lower()), None)
    if not c:
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', entry_id):
            raise SourceError('Invalid GitHub repository')
        entry = _entry(source, {'repo': entry_id, 'name': entry_id}, False)
        return {**entry, 'versions': []}
    entry = _entry(source, c)
    releases = _api('/repos/' + c['repo'] + '/releases?per_page=10')
    versions = []
    for release in releases:
        if release.get('draft') or (release.get('prerelease') and not c.get('allow_prerelease')):
            continue
        assets = [a for a in release.get('assets', []) if
                  fnmatch.fnmatch(a['name'].lower(), c['asset_pattern'].lower())]
        for asset in assets:
            digest = asset.get('digest') or ''
            versions.append({'version': release['tag_name'], 'version_code': None,
                             'asset_id': asset['id'], 'name': asset['name'], 'min_sdk': None,
                             'prerelease': bool(release.get('prerelease')),
                             'size': asset.get('size'), 'updated': release.get('published_at'),
                             'url': asset['browser_download_url'],
                             'sha256': digest[7:] if re.fullmatch(r'sha256:[0-9a-f]{64}', digest) else None})
    entry['versions'] = versions
    entry['downloadable'] = bool(versions)
    if versions:
        entry.update({k: versions[0][k] for k in ('version', 'size', 'updated')})
    return entry


def download(source, entry_id, version_code=None):
    entry = details(source, entry_id)
    versions = entry['versions']
    if not versions:
        raise SourceError('No approved APK release; open the publisher page')
    # GitHub asset IDs and tags are not Android version codes.
    if version_code is not None:
        raise SourceError('GitHub does not publish Android version codes; download the latest release')
    v = versions[0]
    expected = 'https://github.com/' + entry['id'] + '/releases/download/'
    if not v['url'].startswith(expected):
        raise SourceError('APK URL does not belong to the curated publisher')
    return _web.apk(v['url'], HOSTS, v['sha256'], name='GitHub')
