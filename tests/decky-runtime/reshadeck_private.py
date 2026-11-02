"""Actual X11 properties in an authenticated private Xvfb, never host gamescope."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import time

from radiyo_private import identity, descendants

PROPERTY = 'GAMESCOPE_RESHADE_EFFECT'


def command(env, *args):
    return subprocess.check_output(args, env=env, text=True, stderr=subprocess.DEVNULL, timeout=3)


def property_value(env):
    text=command(env,'xprop','-root','-notype',PROPERTY)
    if ' = ' not in text:
        raise RuntimeError('Private X11 property is missing: '+text.strip())
    return json.loads(text.split(' = ',1)[1].strip())


def snapshot(paths):
    return {str(p):dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),inode=p.stat().st_ino,
        mode=p.stat().st_mode,mtimeNs=p.stat().st_mtime_ns)for p in paths}


def start(env, log, processes, until_ready):
    auth=Path('/tmp/framey-private-xauthority');auth.touch(mode=0o600)
    command(env,'xauth','-f',str(auth),'add',':93','.',secrets.token_hex(16))
    env.update(DISPLAY=':93',XAUTHORITY=str(auth))
    # Keep this private session's root properties between short xprop clients.
    xserver=subprocess.Popen(['Xvfb',':93','-noreset','-screen','0','64x64x24','-nolisten','tcp','-auth',str(auth)],
        env=env,stdout=log,stderr=log,start_new_session=True)
    processes.append(xserver)
    def ready():
        try:return bool(command(env,'xdpyinfo'))
        except subprocess.CalledProcessError:return False
    until_ready(ready,'authenticated private X11 display')
    command(env,'xprop','-root','-f',PROPERTY,'8u','-set',PROPERTY,'unmanaged effect.fx')
    dest=Path.home()/'.local/share/gamescope/reshade/Shaders';dest.mkdir(parents=True)
    collision=dest/'RD_MattiasCRT.fx';collision.write_bytes(b'preexisting private shader marker')
    custom=dest/'User shader.fx';custom.write_bytes(b'private user shader marker; no renderer executes this fixture')
    outside=Path.home()/'outside-shader.fx';outside.write_bytes(b'outside private marker')
    (dest/'linked.fx').symlink_to(outside)
    return dict(paths=[collision,custom,outside],before=snapshot([collision,custom,outside]),
        display=':93',authEnabled=True,hostDisplayExposed=False,realFrameContacted=False,
        physicalShaderRenderingVerified=False,initialProperty=property_value(env))


def stop(backend, log, disconnect):
    before=descendants(backend.pid);assert before;closed=[]
    if disconnect:
        paths=list(Path('/tmp').glob('plugin_socket_*'));assert len(paths)==1
        with socket.socket(socket.AF_UNIX)as peer:
            peer.settimeout(.2);peer.connect(str(paths[0]));peer.shutdown(socket.SHUT_WR)
        closed=[str(paths[0])];time.sleep(.05)
    previous=Path(log.name).read_text();started=time.monotonic();backend.send_signal(signal.SIGTERM);backend.wait(timeout=8)
    adopted=[];deadline=time.monotonic()+2
    while True:
        for pid,old in before.items():
            state=identity(pid)
            if state and state['start']==old['start']:
                try:
                    done,status=os.waitpid(pid,os.WNOHANG)
                    if done:adopted.append(dict(pid=done,returncode=os.waitstatus_to_exitcode(status)))
                except ChildProcessError:pass
        remaining={pid:state for pid,old in before.items()if(state:=identity(pid))and state['start']==old['start']}
        if not remaining or time.monotonic()>=deadline:break
        time.sleep(.01)
    console=Path(log.name).read_text()[len(previous):];elapsed=time.monotonic()-started
    assert backend.returncode==0 and elapsed<5 and not remaining
    assert all(v['returncode']==0 for v in adopted)
    assert 'Sending SIGKILL!'not in console and 'Error during shutdown:'not in console
    assert 'Plugin Reshadeck (v0.2.0) has been stopped in 'in console
    return dict(parentOnlySignal=True,returncode=backend.returncode,seconds=elapsed,
        descendantsBefore=before,exactDescendantsRemaining=remaining,adoptedChildExits=adopted,
        closedUnixPeers=closed,console=console,consoleSha256=hashlib.sha256(console.encode()).hexdigest(),
        cleanShutdownVerified=True)


def probe(backend, loader, env, log, processes, legacy, until_ready, fixture, plugin):
    evidence={k:v for k,v in fixture.items()if k!='paths'};evidence.update(properties=[],stops=[])
    expected=['DefringSamsungOLEDeck.fx','RD_MattiasCRT.fx','RD_VHS_RA.fx','User shader.fx','linked.fx']
    until_ready(lambda:legacy('get_shader_list')==expected,'published shader discovery')
    assert legacy('get_screensaver_list')==['SS_ScreenOff.fx']
    assert property_value(env)==fixture['initialProperty']=='unmanaged effect.fx','startup must not clear another effect'
    def prop(expected):
        actual=property_value(env);assert actual==expected;evidence['properties'].append(actual)
    assert legacy('set_shader',shader_name='RD_VHS_RA.fx')is True;prop('RD_VHS_RA.fx')
    assert legacy('get_current_shader')=='RD_VHS_RA.fx'
    assert legacy('set_shader',shader_name='User shader.fx')is True;prop('User shader.fx')
    assert legacy('set_screensaver',shader_name='SS_ScreenOff.fx')is True;prop('User shader.fx')
    assert legacy('get_current_screensaver')=='SS_ScreenOff.fx'
    assert legacy('apply_shader',screensaver=True)is True;prop('SS_ScreenOff.fx')
    assert legacy('apply_shader',screensaver=False)is True;prop('User shader.fx')
    for invalid in ['../outside-shader.fx','missing.fx','linked.fx']:
        assert legacy('set_shader',shader_name=invalid)is False;prop('User shader.fx')
    assert legacy('set_shader',shader_name='0')is True;prop('0')
    assert legacy('set_shader',shader_name='User shader.fx')is True;prop('User shader.fx')
    sibling=subprocess.Popen([sys.executable,'-c','import time; time.sleep(90)'],start_new_session=True)
    processes.append(sibling);sibling_identity=identity(sibling.pid)
    for cycle in range(2):
        evidence['stops'].append(stop(backend,log,disconnect=cycle==0))
        prop('User shader.fx');assert snapshot(fixture['paths'])==fixture['before']
        after=identity(sibling.pid);assert sibling.poll()is None and after and (after['parent'],after['start'])==(sibling_identity['parent'],sibling_identity['start'])
        if cycle==0:
            backend=subprocess.Popen([str(loader)],env=env,stdout=log,stderr=log,start_new_session=True)
            processes.append(backend)
            until_ready(lambda:legacy('get_shader_list')==expected,'shader discovery after restart')
            prop('User shader.fx')
    evidence['sharedFilesAfter']=snapshot(fixture['paths']);evidence['unrelatedSiblingPreserved']=True
    evidence['installedHashes']={p:hashlib.sha256((plugin/p).read_bytes()).hexdigest()
        for p in ['main.py','shaders/set_shader.sh','py_modules/framey_reshadeck.py','py_modules/framey_decky_ipc.py']}
    return evidence
