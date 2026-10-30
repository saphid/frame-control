#!/usr/bin/env python3
"""Exercise the exact Syncthing frontend with private, synthetic RPC responses.

No Decky backend, Syncthing service, Steam session or Frame is contacted.
The optional frontend candidate is uninstalled and admission remains blocked.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ui'))
import framey_panel
import frame_steam

DIGEST = '27e47379c280c92253d5533435f57c33b332b215f866d2ac4493daf18ec0d1c4'
SOURCES = (
    'scripts/framey-test-syncthing-browser.py', 'ui/framey_panel.py', 'ui/framey-host.js',
    'ui/vendor/react-18.3.1.min.js', 'ui/vendor/react-dom-18.3.1.min.js',
    'ui/vendor/syncthing-0.2.7/frontend.patch',
)


def fingerprints():
    return {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCES}


PROBE = r'''
const browserErrors=[];
addEventListener('error',event=>browserErrors.push(event.message));
addEventListener('unhandledrejection',event=>browserErrors.push(String(event.reason)));
addEventListener('message', async event => {
  if (event.source !== parent || event.data?.type !== 'test:run') return;
  const configured = event.data.configured, wizard = event.data.wizard;
  const wait = async read => {const end=Date.now()+5000;while(Date.now()<end){
    if(read())return;await new Promise(resolve=>setTimeout(resolve,25));}throw Error('DOM condition timed out');};
  const deadline = Date.now() + 1500;
  const button = () => [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Start Setup');
  while (!button() && Date.now() < deadline) await new Promise(resolve => setTimeout(resolve, 25));
  const welcome = !!button();
  if (welcome) {
    button().click();
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  let wizardCompleted=false, finishNavigation=false, error=null;
  const installationMethod=document.getElementById('framey-root').innerText.includes('Installation Method');
  try {
    if(welcome && wizard){
      [...document.querySelectorAll('button')].find(b=>b.textContent.includes('"Syncthing GTK" Flatpak')).click();
      await wait(()=>document.getElementById('framey-root').innerText.includes('Almost done!'));
      const select=document.querySelector('select');
      select.value=[...select.options].find(o=>o.textContent.startsWith('At boot')).value;
      select.dispatchEvent(new Event('change',{bubbles:true}));
      document.querySelector('input[type=checkbox]').click();
      await new Promise(resolve=>setTimeout(resolve,50));
      [...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Continue').click();
      await wait(()=>document.getElementById('framey-root').innerText.includes('All done!'));
      wizardCompleted=true;
      if(event.data.finishNavigation){
        [...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Get Started').click();
        await wait(()=>document.getElementById('framey-root').innerText.includes('State request failed. Status: 500'));
        await new Promise(resolve=>setTimeout(resolve,250));
        finishNavigation=!document.getElementById('framey-root').innerText.includes('All done!');
      }
    }
  }catch(err){error=err.message;}
  const text = document.getElementById('framey-root').innerText;
  parent.postMessage({type:'test:done', welcome, installationMethod: text.includes('Installation Method'),
    entryInstallationMethod:installationMethod,wizardCompleted,finishNavigation,error,browserErrors,
    configuredErrorVisible:configured&&text.includes('State request failed. Status: 500'),
    text: text.slice(0,2500), syntheticInput:true, realBackend:false}, '*');
});
'''
PARENT = r'''
const calls=[], settings={config_version:2,mode:'flatpak',flatpak_name:'me.kozec.syncthingtk',
  flatpak_binary:'syncthing',service_name:'',autostart:'no',keep_running_on_desktop:false,
  port:8384,api_key:'',basic_auth_user:'',basic_auth_pass:'',is_setup:SETUP_STATE};
if(settings.is_setup==='migratingV2'){settings.port=8386;settings.api_key='private-legacy-fixture-key';}
let complete=false;
addEventListener('message', event => {
  const target=document.getElementById('panel').contentWindow;
  if(event.source!==target)return;
  const req=event.data||{};
  if(req.type==='framey:cache:init'){target.postMessage({type:'framey:cache:seed',session:req.session,entries:{}},'*');return;}
  if(req.type==='framey:ready'){target.postMessage({type:'test:run',configured:CONFIGURED,wizard:WIZARD,
    finishNavigation:FINISH_NAVIGATION},'*');return;}
  if(req.type==='test:done'){
    complete=true;
    document.getElementById('result').textContent=JSON.stringify({...req,calls,settings});return;
  }
  if(req.type!=='framey:call')return;
  if(calls.length>=100)return; // Bound the published frontend's reload loop.
  calls.push({method:req.method,args:req.args});
  let result;
  if(req.method==='get_settings_json')result={success:true,result:JSON.stringify(settings)};
  else if(req.method==='set_setting' && WIZARD){settings[req.args[0].setting]=req.args[0].value;result={success:true,result:null};}
  else if(req.method==='framey_http_fetch' && WIZARD && req.legacy && req.args[0]?.method==='POST'){
    const values={'/__decky-watchdog/check/start':{success:true},
      '/__decky-watchdog/check/scan_port':{port:8384},
      '/__decky-watchdog/check/scan_api_key':{api_key:'private-fixture-key'},
      '/__decky-watchdog/check/scan_basic_auth':{basic_auth_user:null},
      '/__decky-watchdog/reload-config':null};
    const route=req.args[0]?.path;
    result=Object.hasOwn(values,route)?{success:true,result:{status:values[route]===null?204:200,
      body:values[route]===null?'':JSON.stringify(values[route]),headers:{'content-type':'application/json'}}}:
      {success:false,result:'Synthetic browser fixture refuses other routes'};
  }
  else if(req.method==='framey_http_fetch' && req.legacy && req.args[0]?.method==='GET' &&
          req.args[0]?.path==='/__decky-watchdog/state')result={success:true,result:{status:500,
    body:'Managed Syncthing unit has not been created',headers:{'content-type':'text/plain'}}};
  else result={success:false,result:'Synthetic browser fixture refuses other calls'};
  if(!complete)target.postMessage({type:'framey:reply',id:req.id,result},'*');
});
'''


def frontend(archive, candidate):
    if archive.stat().st_size > 50 * 1024**2:
        raise ValueError('Oversized published archive')
    data = archive.read_bytes()
    if hashlib.sha256(data).hexdigest() != DIGEST:
        raise ValueError('Published Syncthing archive digest mismatch')
    with zipfile.ZipFile(archive) as packed:
        bundle = packed.read('decky-syncthing/dist/index.js')
    if candidate:
        with tempfile.TemporaryDirectory(prefix='framey-syncthing-frontend-') as temporary:
            entry = Path(temporary) / 'index.js'
            entry.write_bytes(bundle)
            subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i',
                            str(ROOT / 'ui/vendor/syncthing-0.2.7/frontend.patch')],
                           cwd=temporary, check=True, capture_output=True, timeout=10)
            bundle = entry.read_bytes()
    return bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--browser', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--candidate', action='store_true')
    profiles = parser.add_mutually_exclusive_group()
    profiles.add_argument('--migrating', action='store_true')
    profiles.add_argument('--configured', action='store_true')
    parser.add_argument('--wizard', action='store_true')
    parser.add_argument('--finish-navigation', action='store_true')
    args = parser.parse_args()
    if args.wizard and args.configured:
        parser.error('Wizard replay requires an incomplete setup profile')
    if args.finish_navigation and not args.wizard:
        parser.error('Finish navigation requires --wizard')
    source_hashes = fingerprints()
    args.output.mkdir(parents=True, exist_ok=False)
    bundle = frontend(args.archive, args.candidate)
    with patch.object(framey_panel, '_owned_dist', return_value=(None, bundle, DIGEST)):
        panel = framey_panel.panel(64).decode()
    for route, name in [('react.js','vendor/react-18.3.1.min.js'),
                        ('react-dom.js','vendor/react-dom-18.3.1.min.js'), ('host.js','framey-host.js')]:
        data = base64.b64encode((ROOT/'ui'/name).read_bytes()).decode()
        panel = panel.replace(f'src="/framey-runtime/{route}"',f'src="data:text/javascript;base64,{data}"')
    panel = panel.replace('</html>', '<script>' + PROBE + '</script></html>')
    parent = PARENT.replace('SETUP_STATE', json.dumps('migratingV2' if args.migrating else args.configured))
    parent = parent.replace('CONFIGURED', json.dumps(args.configured)).replace('WIZARD', json.dumps(args.wizard))
    parent = parent.replace('FINISH_NAVIGATION', json.dumps(args.finish_navigation))
    document = '''<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy"
content="default-src 'none'; script-src 'unsafe-inline' data: blob:; frame-src data:; style-src 'unsafe-inline'; img-src data:">
<title>Private Syncthing setup fixture</title><style>body{margin:0;background:#0d1925;color:white}iframe{width:1200px;height:950px;border:0}pre{white-space:pre-wrap}</style>
<iframe id="panel" sandbox="allow-scripts" src="data:text/html;base64,''' + base64.b64encode(panel.encode()).decode() + '''#fixture"></iframe>
<pre id="result">Pending</pre><script>''' + parent + '</script>'
    with tempfile.TemporaryDirectory(prefix='framey-syncthing-browser-') as temporary:
        folder = Path(temporary)
        source = folder/'fixture.html'
        source.write_text(document)
        command = [str(args.browser.resolve()),'--headless','--disable-gpu','--no-first-run',
                   '--no-default-browser-check','--disable-background-networking','--user-data-dir='+str(folder/'profile'),
                   '--window-size=1240,1200','--remote-debugging-address=127.0.0.1',
                   '--remote-debugging-port=0',source.as_uri()]
        page = None
        with (args.output/'browser.log').open('w+') as log:
            browser = subprocess.Popen(command, stdout=log, stderr=log)
            try:
                deadline = time.monotonic()+20
                report = {'passed':False,'error':'Browser fixture did not finish'}
                while time.monotonic() < deadline:
                    if browser.poll() is not None:
                        log.seek(0)
                        raise RuntimeError(log.read()[-1500:])
                    port = folder/'profile/DevToolsActivePort'
                    if page is None and port.is_file():
                        frame_steam.CDP = 'http://127.0.0.1:'+port.read_text().splitlines()[0]+'/json'
                        try: page = frame_steam.Page('Private Syncthing setup fixture')
                        except (OSError,frame_steam.Fail): pass
                    if page:
                        value = page.eval('document.getElementById("result")?.textContent')
                        if value and value != 'Pending':
                            report = json.loads(value)
                            break
                    time.sleep(.1)
                if page:
                    page.next_id += 1
                    page._send(json.dumps({'id':page.next_id,'method':'Page.captureScreenshot','params':{'format':'png'}}))
                    while True:
                        shot = json.loads(page._recv())
                        if shot.get('id') == page.next_id: break
                    (args.output/'panel.png').write_bytes(base64.b64decode(shot['result']['data']))
            finally:
                if page: page.sock.close()
                browser.terminate()
                try: browser.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    browser.kill(); browser.wait(timeout=5)
        report.update(archiveSha256=DIGEST, frontendSha256=hashlib.sha256(bundle).hexdigest(),
                      candidate=args.candidate, migrating=args.migrating, configured=args.configured,
                      wizard=args.wizard,finishNavigationRequested=args.finish_navigation,realFrameContacted=False,
                      browserReaped=browser.poll() is not None, installerEnabled=False)
        report['browser'] = subprocess.check_output([str(args.browser.resolve()), '--version'], text=True).strip()
        report['sourceSha256'] = source_hashes
        report['sourceUnchanged'] = source_hashes == fingerprints()
        if args.configured:
            state_reads = [call for call in report.get('calls', []) if call['method'] == 'framey_http_fetch']
            report['passed'] = (report.get('configuredErrorVisible') is True
                                and not report.get('welcome') and 0 < len(state_reads) < 5)
        else:
            report['passed'] = report.get('welcome') is True and report.get('entryInstallationMethod') is True
            if args.wizard:
                settings = report.get('settings', {})
                calls = report.get('calls', [])
                routes = [call['args'][0]['path'] for call in calls if call['method'] == 'framey_http_fetch'
                          and call['args'][0]['method'] == 'POST']
                expected_routes = ['/__decky-watchdog/check/' + name for name in
                                   ('start', 'scan_port', 'scan_api_key', 'scan_basic_auth')]
                expected_routes.append('/__decky-watchdog/reload-config')
                completion = [i for i, call in enumerate(calls) if call ==
                              {'method':'set_setting','args':[{'setting':'is_setup','value':True}]}]
                reloads = [i for i, call in enumerate(calls) if call ==
                           {'method':'framey_http_fetch','args':[{'method':'POST',
                            'path':'/__decky-watchdog/reload-config','headers':{}}]}]
                report['passed'] = (report['passed'] and report.get('wizardCompleted') is True
                                    and settings.get('is_setup') is True and settings.get('autostart') == 'boot'
                                    and settings.get('keep_running_on_desktop') is True
                                    and settings.get('api_key') == 'private-fixture-key'
                                    and routes == expected_routes
                                    and settings.get('mode') == 'flatpak'
                                    and settings.get('flatpak_name') == 'me.kozec.syncthingtk'
                                    and len(completion) == 1 and len(reloads) == 1
                                    and completion[0] < reloads[0])
                if args.finish_navigation:
                    report['passed'] = (report['passed'] and report.get('finishNavigation') is True
                                        and report.get('browserErrors') == [])
            else:
                report['passed'] = (report['passed'] and all(call['method'] == 'get_settings_json'
                                                           for call in report.get('calls', [])))
                if args.migrating:
                    report['passed'] = (report['passed'] and report['settings']['port'] == 8386
                                        and report['settings']['api_key'] == 'private-legacy-fixture-key')
        report['passed'] = report['passed'] and report['sourceUnchanged'] and report['browserReaped']
        (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report))
        if not report['passed']: raise SystemExit(1)


if __name__ == '__main__':
    main()
