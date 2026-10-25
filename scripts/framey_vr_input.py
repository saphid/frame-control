"""Headset-side real input exercise, appended after framey_openvr.py by the runner."""
import json
from pathlib import Path
import sys
import time
import urllib.request


def exercise(profile, plugin_id, folder):
    sys.path.insert(0, str(Path.home()/'.local/share/frame-control/headset/bundle/ui'))
    import frame_steam
    port = int((Path(profile)/'DevToolsActivePort').read_text().splitlines()[0])
    frame_steam.CDP = f'http://127.0.0.1:{port}/json'
    parent = frame_steam.Page('Frame Control VR [fc-headset]')
    panel = None
    vr = Overlay()
    result = {'clickTransport':'IVROverlayView_003.PostOverlayEvent',
              'textTransport':'CDP Input.insertText after OpenVR focus',
              'controllerHardwareVerified':False}

    def wait(read, accept, seconds=15):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = read()
            if accept(value): return value
            time.sleep(.25)
        raise RuntimeError('Timed out waiting for live UI: ' + str(value))

    def connect_panel():
        def target():
            targets = json.load(urllib.request.urlopen(frame_steam.CDP, timeout=5))
            return next((p['title'] for p in targets if p.get('type') == 'iframe'
                         and '/framey/panel/' + str(plugin_id) in p.get('url','')), None)
        page = frame_steam.Page(wait(target, bool))
        page.eval('window.__vrClickCount=0;addEventListener("pointerup",e=>{window.__vrClickCount++;window.__vrLastTarget=e.target;});true')
        return page

    def command(page, method, params):
        page.next_id += 1
        page._send(json.dumps({'id':page.next_id,'method':method,'params':params}))
        while True:
            msg = json.loads(page._recv())
            if msg.get('id') == page.next_id:
                if 'error' in msg: raise RuntimeError(str(msg['error']))
                return msg.get('result', {})

    def text(): return panel.eval('document.body.innerText')

    def click(selector):
        # Account for CSS pixels, iframe position, border, HiDPI scaling, and
        # OpenVR's bottom-left mouse origin; read geometry after scrolling.
        panel.eval(f'document.querySelector({json.dumps(selector)}).scrollIntoView({{block:"center"}})')
        time.sleep(.3)  # let Chromium present the scrolled iframe before native input
        pos = panel.eval(f'(()=>{{let r=document.querySelector({json.dumps(selector)}).getBoundingClientRect();return {{x:r.x+r.width/2,y:r.y+r.height/2}}}})()')
        outer = parent.eval('(()=>{let f=byId("frameyFrame"),r=f.getBoundingClientRect();return {x:r.x+f.clientLeft,y:r.y+f.clientTop,w:innerWidth,h:innerHeight}})()')
        sx, sy = vr.snapshot()['input']['scale']
        x = (outer['x'] + pos['x']) * sx / outer['w']
        y = sy - (outer['y'] + pos['y']) * sy / outer['h']
        if not 0 <= x <= sx or not 0 <= y <= sy:
            raise RuntimeError('Control is outside the visible viewport')
        count = panel.eval('__vrClickCount')
        vr.post_mouse(300, x, y)
        vr.post_mouse(301, x, y, 1)
        vr.post_mouse(302, x, y, 1)
        wait(lambda:panel.eval('__vrClickCount'), lambda n:n > count, seconds=3)
        hit = panel.eval(f'!!window.__vrLastTarget?.closest({json.dumps(selector)})')
        if not hit:
            raise RuntimeError('Native click hit another element: ' + str(panel.eval('({tag:__vrLastTarget?.tagName,text:__vrLastTarget?.textContent?.slice(0,100)})')))

    try:
        parent.eval(f'(async()=>{{await refreshDecky();openFrameyPanel({plugin_id},"Framey VR Check");return true}})()')
        wait(lambda:parent.eval('byId("frameyPanelStatus").innerText'), lambda s:s == 'Plugin panel ready')
        panel = connect_panel()
        initial = wait(text, lambda s:'Saved setting: off' in s or 'Could not read setting:' in s)
        if 'Could not read setting:' in initial: raise RuntimeError(initial)
        result['initialText'] = initial
        panel.eval('window.__vrEvents=[];addEventListener("pointerup",e=>__vrEvents.push({trusted:e.isTrusted,x:e.clientX,y:e.clientY}));true')
        click('input[type=checkbox]')
        result['savedText'] = wait(text, lambda s:'Saved setting: on' in s)
        result['pointerEvents'] = panel.eval('__vrEvents')
        result['trustedOverlayPointer'] = any(e['trusted'] for e in result['pointerEvents'])
        disk = Path.home()/'.local/share/frame-control/decky/settings'/folder/'settings.json'
        result['diskSetting'] = json.loads(disk.read_text())
        # Fresh browser document, same normal parent API; no backend stub.
        panel.sock.close(); panel = None
        parent.eval(f'openFrameyPanel({plugin_id},"Framey VR Check")')
        wait(lambda:parent.eval('byId("frameyPanelStatus").innerText'), lambda s:s == 'Plugin panel ready')
        panel = connect_panel()
        result['reopenedText'] = wait(text, lambda s:'Saved setting: on' in s)
        result['reopenedChecked'] = panel.eval('document.querySelector("input[type=checkbox]").checked')
        # Settings tab and quick action are real host controls too.
        click('nav button:nth-child(2)')
        wait(text, lambda s:'Saved setting: on' in s)
        click('nav button:nth-child(1)')
        wait(text, lambda s:'Saved setting: on' in s)
        panel.eval('[...document.querySelectorAll("button")].find(b=>b.textContent==="Read saved setting").id="vr-quick"')
        click('#vr-quick')
        result['quickActionText'] = wait(text, lambda s:'Saved setting is on' in s)
        # Isolated diagnostic controls use the actual shipped DFL shims. Their
        # values are UI-only; they never change a user's settings or plugin.
        panel.eval('''(()=>{
          const mount=document.createElement('div');mount.id='vr-controls';document.body.prepend(mount);
          function Controls(){const R=SP_REACT,[v,S]=R.useState(10),[t,T]=R.useState('');return R.createElement('section',null,
            R.createElement(DFL.SliderField,{label:'VR test slider',min:0,max:100,value:v,showValue:true,onChange:S}),
            R.createElement(DFL.TextField,{label:'VR test text',value:t,onChange:e=>T(e.target.value)}),
            R.createElement('p',{id:'vr-control-values'},v+':'+t));}
          SP_REACTDOM.createRoot(mount).render(SP_REACT.createElement(Controls));return true;
        })()''')
        wait(lambda:panel.eval('!!document.querySelector("#vr-controls input[type=range]")'), bool)
        click('#vr-controls input[type=range]')
        result['sliderValue'] = wait(lambda:panel.eval('document.querySelector("#vr-controls input[type=range]").value'), lambda v:v != '10')
        click('#vr-controls input[type=text]')
        # CDP only types text; OpenVR supplies pointer focus into the field.
        command(parent, 'Input.insertText', {'text':'framey-ci'})
        result['textValue'] = wait(lambda:panel.eval('document.querySelector("#vr-controls input[type=text]").value'), lambda v:v == 'framey-ci')
        panel.eval('document.getElementById("vr-controls").remove()')
        # Scroll saved status into the visible iframe for compositor evidence.
        panel.eval('document.querySelector("[role=status]").scrollIntoView({block:"center"})')
        result['finalOverlay'] = vr.snapshot()
        result['passed'] = (result['trustedOverlayPointer'] and result['diskSetting'] == {'enabled':True}
                            and result['reopenedChecked'] and result['sliderValue'] != '10'
                            and result['textValue'] == 'framey-ci')
        return result
    except Exception as exc:
        result['error'] = str(exc)
        result['passed'] = False
        if panel:
            result['failureText'] = text()
            result['focus'] = panel.eval('({tag:document.activeElement?.tagName,type:document.activeElement?.type})')
        return result
    finally:
        vr.close()
        parent.sock.close()
        if panel: panel.sock.close()
