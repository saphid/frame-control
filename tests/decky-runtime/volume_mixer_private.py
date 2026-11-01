"""Silent private Pulse streams; no host audio, hardware, Bluetooth or UI."""
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from deck_settings_private import identity, descendants


def command(env, *args):
    return subprocess.check_output(args, env=dict(env, LC_ALL='C'), text=True,
                                   stderr=subprocess.DEVNULL, timeout=4)


def start(env, log, processes, until_ready):
    assert env['XDG_RUNTIME_DIR']=='/run/user/1100' and 'PULSE_SERVER' not in env
    env['DBUS_SYSTEM_BUS_ADDRESS']=env['DBUS_SESSION_BUS_ADDRESS']
    for args, ready in [
        (['dbus-daemon','--session','--nofork','--address='+env['DBUS_SESSION_BUS_ADDRESS']], 'bus'),
        (['pipewire'], 'pipewire-0'), (['wireplumber'], None), (['pipewire-pulse'], None)]:
        child=subprocess.Popen(args,env=env,stdout=log,stderr=log,start_new_session=True);processes.append(child)
        if ready: until_ready(lambda:Path('/run/user/1100',ready).is_socket(),'private '+ready)
    def available():
        try:return 'Server Name:' in command(env,'pactl','info')
        except subprocess.CalledProcessError:return False
    until_ready(available,'private Pulse server')
    module=command(env,'pactl','load-module','module-null-sink','sink_name=framey.private-volume')
    command(env,'pactl','set-default-sink','framey.private-volume')
    players=[]
    for name in ['FrameySelected','FrameyUnrelated']:
        with open('/dev/zero','rb')as zero:
            player=subprocess.Popen(['pacat','--playback','--raw','--rate=48000','--channels=2',
                '--client-name='+name,'--stream-name='+name],env=env,stdin=zero,
                stdout=log,stderr=log,start_new_session=True)
        players.append(player);processes.append(player)
    until_ready(lambda:len(json.loads(command(env,'pactl','--format=json','list','sink-inputs')))==2,'two silent Pulse streams')
    return dict(players=players,nullModule=int(module.strip()),privateRuntime=env['XDG_RUNTIME_DIR'],
        privateBus=env['DBUS_SYSTEM_BUS_ADDRESS'],pulseServerOverride=False,realFrameContacted=False,
        hostAudioExposed=False,bluetoothVerified=False,physicalAudioVerified=False,officialUiVerified=False)


def stop(backend, log, disconnect):
    before=descendants(backend.pid);assert before
    peers=[]
    if disconnect:
        paths=list(Path('/tmp').glob('plugin_socket_*'));assert len(paths)==1
        with socket.socket(socket.AF_UNIX)as peer:
            peer.settimeout(.2);peer.connect(str(paths[0]));peer.shutdown(socket.SHUT_WR)
        peers=[str(paths[0])];time.sleep(.05)
    plugin_log=Path('/tmp/VolumeMixer-decky.log');previous_plugin=plugin_log.read_text()
    previous=Path(log.name).read_text();started=time.monotonic()
    backend.send_signal(signal.SIGTERM);backend.wait(timeout=8)
    adopted=[];deadline=time.monotonic()+2
    while True:
        for pid,old in before.items():
            current=identity(pid)
            if current and current['start']==old['start']:
                try:
                    done,status=os.waitpid(pid,os.WNOHANG)
                    if done:adopted.append(dict(pid=done,returncode=os.waitstatus_to_exitcode(status)))
                except ChildProcessError:pass
        remaining={pid:state for pid,old in before.items()if(state:=identity(pid))and state['start']==old['start']}
        if not remaining or time.monotonic()>=deadline:break
        time.sleep(.01)
    console=Path(log.name).read_text()[len(previous):];seconds=time.monotonic()-started
    assert backend.returncode==0 and seconds<5 and not remaining
    assert all(v['returncode']==0 for v in adopted)
    assert 'Sending SIGKILL!'not in console and 'Error during shutdown:'not in console
    assert 'Plugin Volume Mixer (v1.2.1-1) has been stopped in 'in console
    # This published plugin redirects root logging to its own file. Decky's
    # child goodbye is not on stdout; assert its actual unload callback there.
    child_console=plugin_log.read_text()[len(previous_plugin):]
    assert child_console.count('Unloading VolumeMixer')==1,child_console
    return dict(parentOnlySignal=True,returncode=backend.returncode,seconds=seconds,
        descendantsBefore=before,exactDescendantsRemaining=remaining,adoptedChildExits=adopted,
        closedUnixPeers=peers,pluginConsole=child_console,console=console,consoleSha256=hashlib.sha256(console.encode()).hexdigest(),cleanShutdownVerified=True)



def probe(backend, loader, env, log, processes, legacy, rpc, until_ready, fixture, plugin, discovered, *, original=False):
    players=fixture.pop('players')
    evidence=dict(fixture,readbacks=[],stops=[])
    marker=Path.home()/'unrelated-volume-marker';marker.write_bytes(b'private unrelated file')
    before=dict(inode=marker.stat().st_ino,sha256=hashlib.sha256(marker.read_bytes()).hexdigest(),mtimeNs=marker.stat().st_mtime_ns)
    sibling=subprocess.Popen([sys.executable,'-c','import time;time.sleep(100)'],start_new_session=True)
    processes.append(sibling);sibling_before=identity(sibling.pid)
    def independent():
        return json.loads(command(env,'pactl','--format=json','list','sink-inputs'))
    if original:
        response=rpc('loader/call_legacy_plugin_method','Volume Mixer','get_sink_inputs',{})
        assert response==dict(success=False,result='Failed to connect to pulseaudio server'),response
        assert len(independent())==2
        evidence['expectedRegression']=dict(response=response,privatePulseStillHasTwoStreams=True,qualifiedCompatibilityPass=False)
        return evidence
    streams=legacy('get_sink_inputs')
    assert {s['name']for s in streams}=={'FrameySelected','FrameyUnrelated'},streams
    selected=next(s['index']for s in streams if s['name']=='FrameySelected')
    unrelated=next(s['index']for s in streams if s['name']=='FrameyUnrelated')
    original=next(s for s in independent()if s['index']==unrelated)
    for volume in [0,.25,.731,1]:
        assert legacy('set_input_volume',index=selected,volume=volume)is True
        values=independent();active=next(s for s in values if s['index']==selected)
        assert len(active['volume'])==2,active
        assert all(abs(v['value']/65536-volume)<2/65536 for v in active['volume'].values()),active
        assert next(s for s in values if s['index']==unrelated)==original
        observed=next(s for s in legacy('get_sink_inputs')if s['index']==selected)
        assert abs(observed['volume']-volume)<2/65536,observed
        evidence['readbacks'].append(dict(requested=volume,pactl=values,rpc=observed))
    players[0].terminate();players[0].wait(timeout=4)
    until_ready(lambda:len(legacy('get_sink_inputs'))==1,'stopped stream removed')
    evidence['stoppedStreamRemoved']=True
    for cycle in range(2):
        assert legacy('get_sink_inputs')==[next(s for s in streams if s['index']==unrelated)]
        evidence['stops'].append(stop(backend,log,cycle==0))
        assert players[1].poll()is None and independent()==[original]
        state=identity(sibling.pid);assert state and state['start']==sibling_before['start'] and state['parent']==sibling_before['parent']
        assert dict(inode=marker.stat().st_ino,sha256=hashlib.sha256(marker.read_bytes()).hexdigest(),mtimeNs=marker.stat().st_mtime_ns)==before
        if cycle==0:
            backend=subprocess.Popen([str(loader)],env=env,stdout=log,stderr=log,start_new_session=True);processes.append(backend)
            found=until_ready(lambda:rpc('loader/get_plugins'),'restarted Volume Mixer discovery');assert found==discovered
    evidence['unrelatedStreamSiblingAndMarkerPreserved']=True
    evidence['installedHashes']={p:hashlib.sha256((plugin/p).read_bytes()).hexdigest()for p in ['main.py','py_modules/framey_decky_ipc.py']}
    return evidence
