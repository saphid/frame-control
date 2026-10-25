"""Opaque VR frontend host for plugins owned by Frame Control's Decky store."""
import base64
import json
from pathlib import Path
import re
import shlex

import frame_decky


METHOD = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,63}\Z')
PLUGINS = Path.home()/'.local/share/frame-control/decky/plugins'


class PanelError(ValueError):
    pass


def local_bundle(plugin_id):
    """Read only an API v2 bundle with a store receipt; reject linked paths."""
    if type(plugin_id) is not int or plugin_id <= 0 or not PLUGINS.is_dir() or PLUGINS.is_symlink():
        raise FileNotFoundError('Framey plugin unavailable')
    for folder in PLUGINS.iterdir():
        if folder.is_symlink() or not folder.is_dir():
            continue
        receipt = folder/'.frame-control-store.json'
        manifest = folder/'plugin.json'
        dist = folder/'dist'
        entry = dist/'index.js'
        if any(p.is_symlink() for p in (receipt, manifest, dist, entry)):
            continue
        try:
            if not receipt.is_file() or receipt.stat().st_size > 16_384:
                continue
            meta = json.loads(receipt.read_text())
            if not isinstance(meta, dict):
                continue
            if meta.get('storeId') != plugin_id:
                continue
            if not manifest.is_file() or manifest.stat().st_size > 16_384:
                raise FileNotFoundError('Framey plugin manifest unavailable')
            data = json.loads(manifest.read_text())
            if not isinstance(data, dict):
                raise FileNotFoundError('Framey plugin manifest unavailable')
            flags = data.get('flags', [])
            if data.get('api_version') != 2 or not isinstance(flags, list) or any(x in flags for x in ('root', '_root')):
                raise FileNotFoundError('This Decky frontend is not API v2 or needs root')
            if not entry.is_file() or entry.stat().st_size > 8*1024*1024:
                raise FileNotFoundError('Framey plugin frontend unavailable')
            return entry.read_bytes()
        except (OSError, ValueError):
            raise FileNotFoundError('Framey plugin files are invalid')
    raise FileNotFoundError('Plugin is not managed by the Frame Control Decky store')


def panel(plugin_id):
    """The plugin receives no Frame UI key and is sandboxed to an opaque origin."""
    encoded = base64.b64encode(local_bundle(plugin_id)).decode('ascii')
    return ('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Framey plugin</title><style>body{font:21px/1.4 system-ui;background:#0d1925;color:#f3f7fa;margin:0;padding:20px}
button,select,input{font:inherit;min-height:52px;background:#23618c;color:#fff;border:1px solid #72baf0;border-radius:9px;padding:8px}
button:focus-visible,select:focus-visible,input:focus-visible{outline:4px solid #f8d370}button{margin:4px 8px 4px 0}button:disabled{opacity:.55}section{padding:12px;margin:12px 0;background:#1b3042;border-radius:10px}
label{display:grid;gap:6px;margin:10px 0}small{color:#b9c9d6}</style>
<p id="framey-error" role="status"></p><div id="framey-toasts" aria-live="polite"></div><div id="framey-root"></div><div id="framey-modal"></div>
<script id="framey-bundle" type="application/json">''' + encoded + '''</script>
<script src="/framey-runtime/react.js"></script><script src="/framey-runtime/react-dom.js"></script>
<script src="/framey-runtime/host.js"></script></html>''').encode()


METHOD_SCRIPT = r'''
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path.home()/'.local/share/frame-control/headset/bundle/ui'))
from frame_steam import Page
payload = json.loads(sys.argv[1])
expression = "(async()=>{if(!window.DeckyBackend)throw Error('Decky frontend is unavailable in Steam CEF');return await DeckyBackend.call('loader/call_plugin_method'," + json.dumps(payload['name']) + ',' + json.dumps(payload['method']) + ',' + ','.join(json.dumps(x) for x in payload['args']) + ')})()'
page = Page()
try: print(json.dumps({'result':page.eval(expression)}))
finally: page.sock.close()
'''


def call_method(ssh, plugin_id, method, args):
    if type(plugin_id) is not int or plugin_id <= 0:
        raise PanelError('Choose an installed Decky store plugin')
    if not isinstance(method, str) or not METHOD.fullmatch(method):
        raise PanelError('Invalid plugin method')
    if not isinstance(args, list) or len(args) > 8 or len(json.dumps(args)) > 8192:
        raise PanelError('Plugin method arguments are too large')
    found = [p for p in frame_decky.status(ssh)['plugins'] if p.get('storeId') == plugin_id]
    if len(found) != 1:
        raise PanelError('The plugin is not managed by the Frame Control Decky store')
    payload = {'name':found[0]['name'], 'method':method, 'args':args}
    return json.loads(ssh('python3 - ' + shlex.quote(json.dumps(payload)),
                          stdin=METHOD_SCRIPT, timeout=25))
