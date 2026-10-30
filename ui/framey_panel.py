"""Opaque VR frontend host for plugins owned by Frame Control's Decky store."""
import base64
import json
from pathlib import Path
import re
import shlex

import frame_decky
import frame_decky_store


METHOD = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,63}\Z')
EVENT = re.compile(r'[A-Za-z0-9_:/.-]{1,128}\Z')
SESSION = re.compile(r'[A-Za-z0-9_.-]{1,100}\Z')
RECEIPT = re.compile(r'[0-9a-f]{64}\Z')
MODULE_PATH = re.compile(r'[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*/[A-Za-z0-9_.-]+\.js\Z|index\.js\Z')
PLUGINS = Path.home()/'.local/share/frame-control/decky/plugins'


class PanelError(ValueError):
    pass


def _receipt_digest(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16_384:
        raise FileNotFoundError('Framey plugin store receipt unavailable')
    meta = json.loads(path.read_text())
    digest = meta.get('sha256') if isinstance(meta, dict) else None
    if not isinstance(digest, str) or not RECEIPT.fullmatch(digest):
        raise FileNotFoundError('Framey plugin store receipt unavailable')
    return meta, digest


def _owned_dist(plugin_id, expected_receipt=None):
    """Locate a compatible store-owned frontend without following linked paths."""
    if type(plugin_id) is not int or plugin_id <= 0 or not PLUGINS.is_dir() or PLUGINS.is_symlink():
        raise FileNotFoundError('Framey plugin unavailable')
    for folder in PLUGINS.iterdir():
        if folder.is_symlink() or not folder.is_dir():
            continue
        receipt = folder/'.frame-control-store.json'
        manifest = folder/'plugin.json'
        dist = folder/'dist'
        entry = dist/'index.js'
        if any(p.is_symlink() for p in (manifest, dist, entry)):
            continue
        try:
            meta, digest = _receipt_digest(receipt)
        except (OSError, ValueError, UnicodeError):
            continue
        if meta.get('storeId') != plugin_id:
            continue
        try:
            if expected_receipt is not None and digest != expected_receipt:
                raise FileNotFoundError('Framey plugin changed; reopen its panel')
            if not manifest.is_file() or manifest.stat().st_size > 16_384:
                raise FileNotFoundError('Framey plugin manifest unavailable')
            data = json.loads(manifest.read_text())
            if not isinstance(data, dict):
                raise FileNotFoundError('Framey plugin manifest unavailable')
            flags = data.get('flags', [])
            version = data.get('api_version')
            if ((version is not None and (type(version) is not int or version not in (1, 2))) or
                    not isinstance(flags, list) or any(x in flags for x in ('root', '_root'))):
                raise FileNotFoundError('This Decky frontend has an unsupported API or needs root')
            if not entry.is_file() or entry.stat().st_size > 8*1024*1024:
                raise FileNotFoundError('Framey plugin frontend unavailable')
            bundle = entry.read_bytes()
            legacy = re.match(rb'\s*\(function\s*\(', bundle) is not None
            if version is None and not legacy:
                raise FileNotFoundError('This legacy frontend is not a supported Decky IIFE bundle')
            if version == 1 and not legacy:
                marker = b'__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit'
                supported = marker in bundle
                if not supported and b'./chunks/' in bundle:
                    chunks = dist/'chunks'
                    if chunks.is_symlink() or not chunks.is_dir():
                        raise FileNotFoundError('Framey plugin chunks unavailable')
                    files = list(chunks.iterdir())
                    if len(files) > 128:
                        raise FileNotFoundError('Framey plugin has too many chunks')
                    for chunk in files:
                        if chunk.suffix != '.js':
                            continue
                        if chunk.is_symlink() or not chunk.is_file() or chunk.stat().st_size > 8*1024*1024:
                            raise FileNotFoundError('Framey plugin chunk unavailable')
                        if marker in chunk.read_bytes():
                            supported = True
                if not supported:
                    raise FileNotFoundError('This API v1 frontend does not use the supported Decky API bridge')
            if _receipt_digest(receipt) != (meta, digest):
                raise FileNotFoundError('Framey plugin changed; reopen its panel')
            return dist, bundle, digest
        except FileNotFoundError:
            raise
        except (OSError, ValueError):
            raise FileNotFoundError('Framey plugin files are invalid')
    raise FileNotFoundError('Plugin is not managed by the Frame Control Decky store')


def local_bundle(plugin_id):
    """Read a modern Decky bundle with a store receipt; reject linked paths."""
    return _owned_dist(plugin_id)[1]


def local_module(plugin_id, receipt, name):
    """Serve only JavaScript within a store-owned dist directory for module imports."""
    if not isinstance(name, str) or not MODULE_PATH.fullmatch(name):
        raise FileNotFoundError('Framey module path unavailable')
    if not isinstance(receipt, str) or not RECEIPT.fullmatch(receipt):
        raise FileNotFoundError('Framey module receipt unavailable')
    dist, bundle, _ = _owned_dist(plugin_id, receipt)
    if name == 'index.js':
        return bundle
    target = dist
    for part in name.split('/'):
        target = target/part
        if target.is_symlink():
            raise FileNotFoundError('Framey module path unavailable')
    if not target.is_file() or target.stat().st_size > 8*1024*1024:
        raise FileNotFoundError('Framey module unavailable')
    data = target.read_bytes()
    if _receipt_digest(dist.parent/'.frame-control-store.json')[1] != receipt:
        raise FileNotFoundError('Framey plugin changed; reopen its panel')
    return data


def panel(plugin_id):
    """The plugin receives no Frame UI key and is sandboxed to an opaque origin."""
    _, bundle, receipt = _owned_dist(plugin_id)
    encoded = base64.b64encode(bundle).decode('ascii')
    module = f' data-module="/framey/module/{plugin_id}/{receipt}/index.js"' if b'./chunks/' in bundle else ''
    wine_socket = ' data-wine-socket="1"' if plugin_id == 68 and receipt == frame_decky_store.WINE_CELLAR_DIGEST else ''
    syncthing_http = ' data-syncthing-http="1"' if plugin_id == 64 and receipt == frame_decky_store.SYNCTHING_DIGEST else ''
    downloads = ' data-downloads="1"' if plugin_id == 131 and receipt == frame_decky_store.DOWNLOAD_ALL_DIGEST else ''
    return ('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Framey plugin</title><style>body{font:21px/1.4 system-ui;background:#0d1925;color:#f3f7fa;margin:0;padding:20px}
button,select,input{font:inherit;min-height:52px;background:#23618c;color:#fff;border:1px solid #72baf0;border-radius:9px;padding:8px}
button:focus-visible,select:focus-visible,input:focus-visible{outline:4px solid #f8d370}button{margin:4px 8px 4px 0}button:disabled{opacity:.55}section{padding:12px;margin:12px 0;background:#1b3042;border-radius:10px}
label{display:grid;gap:6px;margin:10px 0}small{color:#b9c9d6}
.framey-spinner,.framey-loading{display:grid;place-items:center;min-height:80px}.framey-loading{background:#1b3042}
.framey-status{color:#b9c9d6}.framey-medium{font-size:1em}.framey-footer{padding:12px 0}
.framey-sections,.framey-library{display:flex;flex-direction:column;gap:12px}.framey-actions{display:flex;flex-wrap:wrap;gap:8px}
.framey-action{min-height:52px}.framey-button-child{display:inline-flex;align-items:center;gap:8px}.framey-green{background:#246b42}
.framey-long-title{overflow-wrap:anywhere}.framey-muted{background:#1b3042}.framey-image{max-width:100%;object-fit:contain}
.framey-focus:focus-visible{outline:4px solid #f8d370}
.framey-dialog{position:fixed;inset:12px;margin:0;z-index:100;overflow:auto;box-shadow:0 0 0 24px #0d1925e6}
.framey-dialog[hidden]{display:none}</style>
<p id="framey-error" role="status"></p><div id="framey-toasts" aria-live="polite"></div><div id="framey-root"></div><div id="framey-modal"></div>
<script id="framey-bundle" type="application/json"''' + module + wine_socket + syncthing_http + downloads + '''>''' + encoded + '''</script>
<script src="/framey-runtime/react.js"></script><script src="/framey-runtime/react-dom.js"></script>
<script src="/framey-runtime/host.js"></script></html>''').encode()


METHOD_SCRIPT = r'''
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path.home()/'.local/share/frame-control/headset/bundle/ui'))
from frame_steam import Page
payload = json.loads(__FRAMEY_METHOD_PAYLOAD__)
route = 'loader/call_legacy_plugin_method' if payload.get('legacy') else 'loader/call_plugin_method'
arguments = [payload['name'], payload['method'], *payload['args']]
expression = "(async()=>{if(!window.DeckyBackend)throw Error('Decky frontend is unavailable in Steam CEF');return await DeckyBackend.call(" + ','.join(json.dumps(x) for x in [route, *arguments]) + ')})()'
page = Page()
try: print(json.dumps({'result':page.eval(expression)}))
finally: page.sock.close()
'''


def _current_plugin(ssh, plugin_id, receipt):
    if not isinstance(receipt, str) or not RECEIPT.fullmatch(receipt):
        raise PanelError('Reopen the plugin panel to refresh its store receipt')
    found = [p for p in frame_decky.plugin_status(ssh)['plugins'] if p.get('storeId') == plugin_id]
    if len(found) != 1:
        raise PanelError('The plugin is not managed by the Frame Control Decky store')
    if found[0].get('sha256') != receipt:
        raise PanelError('The plugin changed; close and reopen its panel')
    return found[0]


def call_method(ssh, plugin_id, method, args, legacy=False, receipt=None):
    if type(plugin_id) is not int or plugin_id <= 0:
        raise PanelError('Choose an installed Decky store plugin')
    if not isinstance(method, str) or not METHOD.fullmatch(method):
        raise PanelError('Invalid plugin method')
    if not isinstance(args, list) or len(args) > 8 or len(json.dumps(args).encode('utf-8')) > 256*1024:
        raise PanelError('Plugin method arguments are too large')
    if type(legacy) is not bool or (legacy and (len(args) != 1 or not isinstance(args[0], dict))):
        raise PanelError('Legacy plugin methods need one keyword argument object')
    plugin = _current_plugin(ssh, plugin_id, receipt)
    if method.startswith('framey_ws_') and (
            method not in {'framey_ws_open', 'framey_ws_send', 'framey_ws_poll', 'framey_ws_close'} or
            plugin_id != 68 or receipt != frame_decky_store.WINE_CELLAR_DIGEST or
            'wine-cellar-native-bridge' not in plugin.get('compatShims', [])):
        raise PanelError('This plugin does not have the Wine Cellar socket bridge')
    if method.startswith('framey_http_') and (
            method != 'framey_http_fetch' or not legacy or plugin_id != 64
            or receipt != frame_decky_store.SYNCTHING_DIGEST
            or 'syncthing-owned-native-http' not in plugin.get('compatShims', [])):
        raise PanelError('This plugin does not have the Syncthing HTTP bridge')
    payload = {'name':plugin['name'], 'method':method, 'args':args, 'legacy':legacy}
    # Library-sized arguments can exceed the OS limit for a single SSH command
    # argument. Send them as a quoted Python literal on stdin instead.
    script = METHOD_SCRIPT.replace('__FRAMEY_METHOD_PAYLOAD__', repr(json.dumps(payload)))
    return json.loads(ssh('python3 -', stdin=script, timeout=25))


# Only parameterless read APIs. Never resolve a plugin-supplied property path
# against SteamClient or evaluate a plugin-supplied expression in trusted CEF.
STEAM_READS = {
    'GetIPCountry': 'SteamClient.User.GetIPCountry()',
    'GetInstallFolders': 'SteamClient.InstallFolder.GetInstallFolders()',
    'GetSystemInfo': 'SteamClient.System.GetSystemInfo()',
    'GetGlobalCompatTools': 'SteamClient.Settings.GetGlobalCompatTools()',
    # Copy selected scalar fields, never Steam objects, methods, credentials or
    # paths. Only the current public Steam ID is needed for per-user plugin data.
    # Compact rows keep even a large library inside the response budget.
    'GetLibrarySnapshot': r'''(()=>{
        if (!window.appStore?.allApps || !window.collectionStore?.allGamesCollection?.allApps)
            throw Error('Steam library is unavailable');
        const apps = Array.from(appStore.allApps);
        if (apps.length > 10000) throw Error('Steam library exceeds the Framey snapshot limit');
        return {apps:apps.map(a=>[a.appid,a.display_name,a.sort_as,a.app_type,String(a.gameid),
            a.minutes_playtime_forever,a.minutes_playtime_last_two_weeks,a.rt_last_time_played,
            typeof a.local_per_client_data?.installed === 'boolean' ? a.local_per_client_data.installed : null]),
            gameIds:Array.from(collectionStore.allGamesCollection.allApps,a=>a.appid),
            steamId:window.App?.m_CurrentUser?.strSteamID || null};
    })()''',
}
STEAM_READ_SCRIPT = r'''
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path.home()/'.local/share/frame-control/headset/bundle/ui'))
from frame_steam import Page
page = Page()
try:
    encoded = json.dumps({'result':page.eval(__FRAMEY_STEAM_READ__)})
    if len(encoded.encode('utf-8')) > __FRAMEY_STEAM_LIMIT__:
        raise ValueError('Steam read response is too large')
    print(encoded)
finally: page.sock.close()
'''


def read_steam(ssh, plugin_id, method, receipt=None):
    """Read one explicitly supported Steam API for an installed store panel."""
    if type(plugin_id) is not int or plugin_id <= 0:
        raise PanelError('Choose an installed Decky store plugin')
    if not isinstance(method, str) or method not in STEAM_READS:
        raise PanelError('This Steam API is unavailable in Framey')
    _current_plugin(ssh, plugin_id, receipt)
    if method == 'GetGlobalCompatTools' and (plugin_id != 68 or receipt != frame_decky_store.WINE_CELLAR_DIGEST):
        raise PanelError('This Steam read is only available to the pinned Wine Cellar panel')
    expression = '(async()=>await ' + STEAM_READS[method] + ')()'
    script = STEAM_READ_SCRIPT.replace('__FRAMEY_STEAM_READ__', repr(expression)).replace(
        '__FRAMEY_STEAM_LIMIT__', str(2*1024*1024 if method == 'GetLibrarySnapshot' else 256*1024))
    return json.loads(ssh('python3 -', stdin=script, timeout=25))


EVENT_SCRIPT = r'''
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path.home()/'.local/share/frame-control/headset/bundle/ui'))
from frame_steam import Page
payload = json.loads(sys.argv[1])
source = __FRAMEY_EVENTS_SOURCE__
page = Page()
try: print(json.dumps(page.eval('(' + source + ')(' + json.dumps(payload) + ')')))
finally: page.sock.close()
'''


def poll_events(ssh, plugin_id, session, events, cursor=0, receipt=None):
    """Read only this store-owned plugin's subscribed events; never trust its claimed name."""
    if type(plugin_id) is not int or plugin_id <= 0:
        raise PanelError('Choose an installed Decky store plugin')
    if not isinstance(session, str) or not SESSION.fullmatch(session):
        raise PanelError('Invalid Framey event session')
    if (not isinstance(events, list) or len(events) > 32 or
            any(not isinstance(event, str) or not EVENT.fullmatch(event) for event in events)):
        raise PanelError('Invalid Decky event names')
    if type(cursor) is not int or not 0 <= cursor <= 9007199254740991:
        raise PanelError('Invalid Decky event cursor')
    plugin = _current_plugin(ssh, plugin_id, receipt)
    payload = {'name':plugin['name'], 'session':session, 'events':events, 'cursor':cursor}
    # Embed only our bundled source as a Python string; plugin data stays in JSON.
    source = Path(__file__).with_name('framey-events.js').read_text(encoding='utf-8')
    script = EVENT_SCRIPT.replace('__FRAMEY_EVENTS_SOURCE__', repr(source))
    return json.loads(ssh('python3 - ' + shlex.quote(json.dumps(payload)), stdin=script, timeout=25))


def poll_running(ssh, plugin_id, session, active, cursor=0, receipt=None):
    """Project running apps and actual lifetime events for one installed panel."""
    if type(plugin_id) is not int or plugin_id <= 0:
        raise PanelError('Choose an installed Decky store plugin')
    if not isinstance(session, str) or not SESSION.fullmatch(session):
        raise PanelError('Invalid Framey running session')
    if type(active) is not bool or type(cursor) is not int or not 0 <= cursor <= 9007199254740991:
        raise PanelError('Invalid Framey running request')
    _current_plugin(ssh, plugin_id, receipt)
    payload = {'pluginId':plugin_id, 'session':session, 'active':active, 'cursor':cursor}
    source = Path(__file__).with_name('framey-running.js').read_text(encoding='utf-8')
    expression = '(' + source + ')(' + json.dumps(payload) + ')'
    script = STEAM_READ_SCRIPT.replace('__FRAMEY_STEAM_READ__', repr(expression)).replace(
        '__FRAMEY_STEAM_LIMIT__', str(256*1024))
    return json.loads(ssh('python3 -', stdin=script, timeout=25))


def downloads(ssh, plugin_id, session, action, appids=None, revision=None, receipt=None):
    """Only the exact managed Download All panel may change local download queues."""
    if type(plugin_id) is not int or plugin_id != 131 or receipt != frame_decky_store.DOWNLOAD_ALL_DIGEST:
        raise PanelError('Download controls require the pinned Download All panel')
    if not isinstance(session, str) or not SESSION.fullmatch(session) or action not in ('read', 'queue', 'close'):
        raise PanelError('Invalid download panel request')
    if action == 'queue':
        if (not isinstance(appids, list) or not 1 <= len(appids) <= 2048 or
                any(type(appid) is not int or not 1 <= appid <= 4294967295 for appid in appids) or
                len(set(appids)) != len(appids) or type(revision) is not int or not 1 <= revision <= 9007199254740991):
            raise PanelError('Choose unique local download app IDs')
    elif appids is not None or revision is not None:
        raise PanelError('Download reads do not accept action arguments')
    plugin = _current_plugin(ssh, plugin_id, receipt)
    if 'download-all-local-queue' not in plugin.get('compatShims', []):
        raise PanelError('Update or reinstall Download All before opening its panel')
    source = Path(__file__).with_name('framey-downloads.js').read_text(encoding='utf-8')
    expression = '(' + source + ')(' + json.dumps({'session':session, 'action':action,
                                                'appids':appids, 'revision':revision}) + ')'
    script = STEAM_READ_SCRIPT.replace('__FRAMEY_STEAM_READ__', repr(expression)).replace(
        '__FRAMEY_STEAM_LIMIT__', str(1024*1024))
    return json.loads(ssh('python3 -', stdin=script, timeout=25))
