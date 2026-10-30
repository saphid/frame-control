"""Unchanged production browser parent, with fixture CEF/receipt in the owned VM."""
import json
import os
from pathlib import Path


def command(page, method, params, session_id=None):
    page.next_id += 1
    request = dict(id=page.next_id, method=method, params=params)
    if session_id is not None:
        request['sessionId'] = session_id
    page._send(json.dumps(request))
    while True:
        reply = json.loads(page._recv())
        if reply.get('id') == page.next_id:
            assert 'error' not in reply, reply
            return reply['result']


def install_child_harness(page, panel_url, source,
                          ready_expression="typeof window.manualPortFallbackUsed==='boolean'"):
    # Sandboxed panels can be out-of-process iframes. A new-document script
    # registered on the parent does not install a driver in that target.
    targets = command(page, 'Target.getTargets', {})['targetInfos']
    matches = [target for target in targets
               if target['type'] == 'iframe' and target['url'] == panel_url]
    assert len(matches) <= 1
    session = None
    params = dict(expression=source+';('+ready_expression+')',
                  returnByValue=True, awaitPromise=True)
    try:
        if matches:
            session = command(page, 'Target.attachToTarget',
                              dict(targetId=matches[0]['targetId'], flatten=True))['sessionId']
            mode = 'owned-iframe-target'
        else:
            frames = []
            def visit(tree):
                if tree['frame']['url'] == panel_url:
                    frames.append(tree['frame']['id'])
                for child in tree.get('childFrames', []):
                    visit(child)
            visit(command(page, 'Page.getFrameTree', {})['frameTree'])
            assert len(frames) == 1, 'Owned panel frame not found'
            # This world has no universal-access grant. The driver only reads
            # the panel DOM and clicks its controls; application state is real.
            world = command(page, 'Page.createIsolatedWorld',
                            dict(frameId=frames[0], worldName='owned-panel-dom-driver'))
            params['contextId'] = world['executionContextId']
            mode = 'owned-frame-isolated-world'
        result = command(page, 'Runtime.evaluate', params, session)
        assert 'exceptionDetails' not in result, result.get('exceptionDetails')
        assert result['result'].get('value') is True
        return dict(installed=True, mode=mode, universalAccessGranted=False)
    finally:
        if session is not None:
            command(page, 'Target.detachFromTarget', dict(sessionId=session))


def sandboxed_renderers(browser_pid):
    renderers = []
    for process in Path('/proc').iterdir():
        if not process.name.isdecimal():
            continue
        try:
            args = (process/'cmdline').read_bytes().replace(b'\0', b' ').split()
            if b'--type=renderer' not in args:
                continue
            chain = [int(process.name)]
            while chain[-1] != browser_pid:
                parent = int(Path('/proc/'+str(chain[-1])+'/stat').read_text().rsplit(')', 1)[1].split()[1])
                assert parent > 1 and parent not in chain and len(chain) < 16
                chain.append(parent)
            status = (process/'status').read_text()
            assert 'Seccomp:\t2\n' in status and 'NoNewPrivs:\t1\n' in status
            renderers.append(dict(pid=int(process.name), ancestryToBrowser=chain, seccomp=2, noNewPrivs=1))
        except FileNotFoundError:
            continue
    assert renderers
    return renderers


def exercise(cef, base, ui_key, browser_pid, legacy_rpc, runtime_identity, service):
    assert os.getuid() == 1100 and Path('/framey-owned-vm').read_text() == 'Frame Control Flatpak VM v1\n'
    assert not Path('/sys/class/net/eth0').exists()
    import frame_steam
    from syncthing_browser import PROBE, screenshot
    from syncthing_service import prop, wait
    assert prop('frame-control-decky.service', 'ActiveState') == 'active'
    decky_pid = int(prop('frame-control-decky.service', 'MainPID'))
    assert decky_pid > 0
    assert Path('/proc/'+str(decky_pid)+'/exe').resolve() == Path.home()/'decky/PluginLoader'
    discovered = cef.eval("DeckyBackend.call('loader/get_plugins')")
    assert any(plugin['name'] == 'Syncthing' for plugin in discovered)
    legacy_rpc('set_setting', setting='is_setup', value=False)
    legacy_rpc('set_setting', setting='api_key', value='')
    # Only DOM input and evidence collection are injected. The HTTP-served
    # production parent, panel generation and runtime scripts are unchanged.
    bootstrap = "if(location.pathname==='/headset'){"+r'''
window.parentProbeStage=null;window.parentProbeFailure=null;window.parentProbeErrors=[];
addEventListener('error',e=>parentProbeErrors.push(e.message));
addEventListener('unhandledrejection',e=>parentProbeErrors.push(String(e.reason)));
addEventListener('securitypolicyviolation',e=>parentProbeErrors.push('CSP '+e.violatedDirective));
addEventListener('message',e=>{
 if(e.source!==document.getElementById('frameyFrame')?.contentWindow)return;
 if(e.data?.type==='test:stage')window.parentProbeStage=e.data;
 if(e.data?.type==='test:failure')window.parentProbeFailure=e.data.error;
});
window.parentProbeAdvance=action=>{window.parentProbeStage=null;
 document.getElementById('frameyFrame').contentWindow.postMessage({type:'test:advance',action},'*');};
}'''
    target = command(cef, 'Target.createTarget', dict(url=base+'/parent-bootstrap'))['targetId']
    page = None
    report = dict(success=False, syntheticInput=True, syntheticCef=True,
                  syntheticStoreReceipt=True, realSteamCef=False, realFrameContacted=False,
                  managedInstallVerified=False, installerEnabled=False,
                  productionParentUnchanged=True, productionPanelUnchanged=True,
                  actualDeckyUserService=True, actualDeckyDiscovery=True, deckyMainPid=decky_pid,
                  bootstrapStateInjected=False, browserSandboxDisabled=False)
    stages, shots, observations = [], {}, []
    try:
        def opened():
            nonlocal page
            try:
                page = frame_steam.Page('Owned HTTP parent bootstrap')
                return True
            except (OSError, frame_steam.Fail):
                return False
        wait(opened, 'owned production parent browser target')
        command(page, 'Page.enable', {})
        command(page, 'Page.addScriptToEvaluateOnNewDocument', dict(source=bootstrap))
        command(page, 'Emulation.setDeviceMetricsOverride',
                dict(width=1240, height=1400, deviceScaleFactor=1, mobile=False))
        command(page, 'Page.navigate', dict(url=base+'/headset#'+ui_key))
        wait(lambda: page.eval("typeof window.parentProbeAdvance==='function'"),
             'DevTools parent input/evidence harness')
        def listed():
            return page.eval("!![...document.querySelectorAll('#deckyInstalled button')].find(b=>b.textContent==='Open panel'&&!b.disabled)")
        wait(listed, 'production installed plugin list with actual Decky user service')
        page.eval("[...document.querySelectorAll('#deckyInstalled button')].find(b=>b.textContent==='Open panel').click()")
        wait(lambda: page.eval("document.getElementById('frameyPanelStatus')?.textContent==='Plugin panel ready'"),
             'unchanged production parent and panel readiness')
        frame = page.eval("({sandbox:document.getElementById('frameyFrame').getAttribute('sandbox'),src:new URL(document.getElementById('frameyFrame').src).pathname})")
        assert frame == dict(sandbox='allow-scripts allow-popups', src='/framey/panel/64')
        panel_url = page.eval("document.getElementById('frameyFrame').src")
        # Each DOM wait may cross several production HTTP/SSH requests.
        # This changes only the input/evidence driver's bounded wait budget.
        assert PROBE.count('const end=Date.now()+60000') == 1
        driver = PROBE.replace('const end=Date.now()+60000', 'const end=Date.now()+120000')
        report['childHarness'] = install_child_harness(page, panel_url, driver)
        report['childHarness']['domWaitMilliseconds'] = 120000
        previous = []
        for label, action in [('running', 'setup'), ('stopped', 'stop'), ('restarted', 'start'), ('stopped', 'stop')]:
            page.eval('window.parentProbeAdvance('+json.dumps(action)+')')
            def advanced():
                failure = page.eval('window.parentProbeFailure')
                assert failure is None, failure
                return page.eval('window.parentProbeStage')
            # A complete setup crosses many production HTTP/SSH RPCs. Keep a
            # bounded stage budget separate from each individual DOM wait.
            stage = wait(advanced, 'production parent browser '+label,
                         timeout=180 if action == 'setup' else 90)
            assert stage['stage'] == label and not stage['errors'], stage
            stages.append(stage)
            if label == 'stopped':
                assert prop(service, 'MainPID') == '0'
                assert all(not Path('/proc/'+str(pid)).exists() for pid in previous)
            else:
                pids = runtime_identity(service)
                assert not previous or previous[0] != pids[0]
                previous = pids
                observations.append(dict(stage=label, pids=pids))
            shots[label+str(len(stages))] = screenshot(page)
        errors = page.eval('window.parentProbeErrors')
        assert not errors, errors
        report.update(stages=stages, screenshots=shots, actualPackagedProcessObservations=observations,
                      sandboxedRendererPids=sandboxed_renderers(browser_pid),
                      manualPortFallbackUsed=stages[0]['manualPortFallbackUsed'],
                      parentErrors=errors, iframe=frame, success=True)
    finally:
        report.update(stages=stages, actualPackagedProcessObservations=observations)
        if page:
            if not report['success']:
                try:
                    report['parentStatus'] = page.eval("({panel:document.getElementById('frameyPanelStatus')?.textContent,installed:document.getElementById('deckyInstalled')?.innerText,errors:window.parentProbeErrors,stage:window.parentProbeStage})")
                except (OSError, frame_steam.Fail):
                    report['parentStatusUnavailable'] = True
                try:
                    capture = screenshot(page)
                    chunks = [capture[offset:offset+4096] for offset in range(0, len(capture), 4096)]
                    for index, data in enumerate(chunks):
                        print('FRAMEY_HTTP_PARENT_FAILURE_SCREENSHOT_CHUNK_JSON='+json.dumps(
                            dict(index=index, total=len(chunks), data=data)), flush=True)
                except (OSError, frame_steam.Fail):
                    report['failureScreenshotUnavailable'] = True
            page.sock.close()
        report['ownedTargetClosed'] = command(cef, 'Target.closeTarget', dict(targetId=target))['success']
        print('FRAMEY_HTTP_PARENT_PROGRESS_JSON='+json.dumps({k:v for k,v in report.items() if k!='screenshots'}), flush=True)
    assert report['ownedTargetClosed']
    return report
