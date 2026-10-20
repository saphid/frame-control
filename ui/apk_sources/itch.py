"""Free Android VR RSS listings, plus the Android builds of games the user owns.

The free feeds' download pages stay in the publisher's UI. Owned games appear only
after the user connects their itch.io account with an API key (_itch_account.py);
they download through itch.io's own API, with the download key of that purchase.
"""
import html, re, urllib.parse, xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from . import SourceError, _itch_account, _web

KIND = 'itch'
FEEDS = ('openxr', 'oculus-quest')
OWNED = 'itch-owned'
OWNED_LABEL = 'Owned on itch.io'


def sources():
    found = [{'id': KIND if tag == 'openxr' else 'itch-quest', 'kind': KIND,
              'name': 'itch.io (' + tag + ')', 'url': 'https://itch.io', 'tag': tag,
              'builtin': True, 'enabled': True, 'trust': 'community'} for tag in FEEDS]
    if _itch_account.connected():
        found.append({'id': OWNED, 'kind': KIND, 'name': 'itch.io (my purchases)',
                      'url': 'https://itch.io/my-purchases', 'owned': True,
                      'description': 'Android builds of games you own on itch.io',
                      'builtin': True, 'enabled': True, 'trust': 'user'})
    return found


def _itch_page(url):
    p = urllib.parse.urlsplit(url if isinstance(url, str) else '')
    return p.scheme == 'https' and (p.hostname or '').endswith('.itch.io') and not p.username and ':' not in p.netloc


def _parse(source, data):
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise SourceError('Invalid itch.io RSS feed') from e
    entries = []
    for item in root.findall('./channel/item'):
        page = item.findtext('link') or ''
        if not _itch_page(page):
            continue
        if item.findtext('price') != '$0.00' or item.findtext('platforms/android') != 'yes':
            continue
        cover = item.findtext('imageurl') or None
        if cover and not cover.startswith('https://img.itch.zone/'):
            cover = None
        updated = None
        try:
            updated = parsedate_to_datetime(item.findtext('updateDate')).date().isoformat()
        except (ValueError, TypeError, AttributeError):
            pass
        entries.append({'source': source['id'], 'id': page, 'package': None,
                        'name': item.findtext('plainTitle') or item.findtext('title') or page,
                        'summary': html.unescape(re.sub('<[^>]*>', '', item.findtext('description') or '')).strip(),
                        'icon': cover, 'images': {'icon': cover, 'banner': cover, 'screenshots': []},
                        'page': page, 'version': None, 'version_code': None, 'min_sdk': None,
                        'abis': None, 'vr': True, 'size': None, 'free': True, 'license': None,
                        'updated': updated, 'downloadable': False})
    return entries


def _owned_entry(source, key):
    """Entry for one owned download key, or None if its game isn't for Android."""
    game = key.get('game') if isinstance(key.get('game'), dict) else {}
    game_id = key.get('game_id') or game.get('id')
    if type(game_id) is not int or type(key.get('id')) is not int:
        return None
    traits = game.get('traits')
    if isinstance(traits, list) and 'p_android' not in traits:
        return None  # the game's page offers no Android download
    cover = game.get('cover_url') if isinstance(game.get('cover_url'), str) else None
    if cover and not cover.startswith('https://img.itch.zone/'):
        cover = None
    user = game.get('user') if isinstance(game.get('user'), dict) else {}
    price = game.get('min_price')
    return {'source': source['id'], 'id': str(game_id), 'package': None,
            'name': str(game.get('title') or 'itch.io game ' + str(game_id)),
            'summary': str(game.get('short_text') or OWNED_LABEL),
            'developer': user.get('display_name') or user.get('username'),
            'icon': cover, 'images': {'icon': cover, 'banner': cover, 'screenshots': []},
            'page': game['url'] if _itch_page(game.get('url')) else None,
            'version': None, 'version_code': None, 'min_sdk': None, 'abis': None,
            'vr': None, 'size': None, 'free': price == 0 if type(price) is int else None,
            'owned': True, 'owned_label': OWNED_LABEL, 'license': None,
            'updated': str(game.get('published_at') or '')[:10] or None,
            'downloadable': None, 'download_key_id': key['id']}


def _owned(source):
    entries = {}
    for key in _itch_account.owned_keys():
        entry = _owned_entry(source, key)
        if entry:
            entries.setdefault(entry['id'], entry)  # keys come newest first; one entry per game
    return entries


def search(source, query, limit=50):
    limit = max(0, min(int(limit), 100))
    if not limit:
        return []
    if source.get('owned'):
        entries = _owned(source)
    else:
        entries = {}
        tag = source.get('tag', 'openxr')
        if tag not in FEEDS:
            raise SourceError('Unsupported itch.io feed')
        url = 'https://itch.io/games/free/platform-android/tag-' + tag + '.xml'
        for entry in _parse(source, _web.read(url, ('itch.io',), name='itch.io')):
            entries.setdefault(entry['id'], entry)
    words = query.lower().split()
    return [e for e in entries.values() if all(w in (e['name'] + ' ' + e['summary']).lower()
                                               for w in words)][:limit]


def _owned_details(source, entry_id):
    entry = _owned(source).get(str(entry_id))
    if not entry:
        raise SourceError('This game is not among the Android games you own on itch.io')
    uploads = _itch_account.uploads(int(entry['id']), entry['download_key_id'])
    versions = [{'version': str(u.get('display_name') or u.get('filename') or u['id']), 'version_code': None,
                 'upload_id': u['id'], 'name': u.get('filename'), 'min_sdk': None,
                 'demo': u.get('demo') is True or 'demo' in (u.get('traits') or []),
                 'size': u.get('size') if type(u.get('size')) is int else None,
                 'updated': str(u.get('updated_at') or u.get('created_at') or '')[:10] or None}
                for u in _itch_account.android_uploads(uploads)]
    entry = dict(entry, versions=versions, downloadable=bool(versions))
    if versions:
        entry.update({k: versions[0][k] for k in ('version', 'size', 'updated')})
    return entry


def details(source, entry_id):
    if source.get('owned'):
        return _owned_details(source, entry_id)
    entry = next((e for e in search(source, '', 100) if e['id'] == entry_id), None)
    if not entry:
        raise SourceError('Game is not in the current free Android VR feed; open its publisher page')
    return {**entry, 'versions': []}


def download(source, entry_id, version_code=None):
    if not source.get('owned'):
        raise SourceError('Open the itch.io publisher page to download; automated download pages are disallowed by robots rules')
    if version_code is not None:
        raise SourceError('itch.io does not publish Android version codes; download the latest upload')
    entry = _owned_details(source, entry_id)
    if not entry['versions']:
        raise SourceError('This game has no Android download on itch.io')
    return _itch_account.download(entry['versions'][0]['upload_id'], entry['download_key_id'])
