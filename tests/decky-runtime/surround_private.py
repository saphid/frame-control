"""Private PipeWire/Pulse and actual Decky RPC, with no host audio/session socket."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from radiyo_private import identity, descendants


def command(env, *args):
    return subprocess.check_output(args, env=dict(env, LC_ALL='C'), stderr=subprocess.DEVNULL,
                                   text=True, timeout=4)


def start(env, log, processes, until_ready):
    home = Path.home()
    shared = home/'.config/pipewire/hrir.wav'
    unit = home/'.config/systemd/user/virtual-surround-sound.service'
    for path, data in [(shared,b'unmanaged private HRIR marker'),(unit,b'unmanaged private unit marker')]:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data)
    files = {str(p):dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),inode=p.stat().st_ino,
                        mode=p.stat().st_mode,mtimeNs=p.stat().st_mtime_ns)for p in [shared,unit]}
    for args in [
        ['dbus-daemon','--session','--nofork','--address='+env['DBUS_SESSION_BUS_ADDRESS']],
        ['pipewire'],['wireplumber'],['pipewire-pulse']]:
        child=subprocess.Popen(args,env=env,stdout=log,stderr=log,start_new_session=True)
        processes.append(child)
        if args[0]=='dbus-daemon':until_ready(lambda: Path('/run/user/1100/bus').is_socket(),'private audio session bus')
        if args[0]=='pipewire':until_ready(lambda: Path('/run/user/1100/pipewire-0').is_socket(),'private PipeWire')
    def pulse():
        try:return 'Server Name:' in command(env,'pactl','info')
        except subprocess.CalledProcessError:return False
    until_ready(pulse,'private Pulse compatibility server')
    null=command(env,'pactl','load-module','module-null-sink','sink_name=input.virtual-sink')
    return dict(files=files,nullModule=int(null.strip()),pipewireVersion=command(env,'pipewire','--version'),
                realFrameContacted=False,hostAudioSocketExposed=False,physicalAudioVerified=False)


def stop(backend, log):
    before=descendants(backend.pid);assert before
    old=Path(log.name).read_text();started=time.monotonic();backend.send_signal(signal.SIGTERM);backend.wait(timeout=8)
    adopted=[];deadline=time.monotonic()+2
    while True:
        for pid,info in before.items():
            state=identity(pid)
            if state and state['start']==info['start']:
                try:
                    done,status=os.waitpid(pid,os.WNOHANG)
                    if done:adopted.append(dict(pid=done,returncode=os.waitstatus_to_exitcode(status)))
                except ChildProcessError:pass
        remaining={pid:state for pid,info in before.items()if(state:=identity(pid))and state['start']==info['start']}
        if not remaining or time.monotonic()>=deadline:break
        time.sleep(.01)
    console=Path(log.name).read_text()[len(old):]
    assert backend.returncode==0 and not remaining and all(p['returncode']==0 for p in adopted)
    assert 'Sending SIGKILL!'not in console and 'Error during shutdown:'not in console
    assert 'Plugin Virtual Surround Sound (v0.0.5) has been stopped in 'in console
    return dict(parentOnlySignal=True,returncode=backend.returncode,descendantsBefore=before,
                exactDescendantsRemaining=remaining,adoptedChildExits=adopted,seconds=time.monotonic()-started,
                console=console,consoleSha256=hashlib.sha256(console.encode()).hexdigest(),cleanShutdownVerified=True)


def probe(backend, loader, env, log, processes, current, until_ready, fixture, plugin):
    evidence=dict(fixture,stops=[],sinkReadbacks=[],routingReadbacks=[],presets=[],unrelatedSiblingPreserved=False)
    def sink():
        values=current('get_sinks')
        found=next((s for s in values if s['name']=='input.virtual-surround-sound'),None)
        if found:evidence['sinkReadbacks'].append(values)
        return found
    surround=until_ready(sink,'published backend private surround sink')
    presets=current('get_hrir_file_list');assert len(presets)==11
    assert current('get_enabled_apps_list')==[]
    # A real Pulse stream, targeting no device outside this container.
    with open('/dev/zero','rb')as zero:
        player=subprocess.Popen(['pacat','--playback','--raw','--rate=48000','--channels=2',
            '--client-name=FrameyPrivate','--stream-name=FrameyPrivate'],env=env,
            stdin=zero,stdout=log,stderr=log,start_new_session=True)
    processes.append(player)
    def stream():
        return next((s for s in current('get_sink_inputs')if s['name']=='FrameyPrivate'),None)
    active=until_ready(stream,'actual Pulse stream')
    assert current('enable_for_app','FrameyPrivate')is True
    routed=until_ready(lambda:(v if(v:=stream())and v['sink']==surround['index']else None),'stream routed to surround')
    evidence['routingReadbacks'].append(routed)
    assert current('disable_for_app','FrameyPrivate')is True
    neutral=next(s for s in current('get_sinks')if s['name']=='input.virtual-sink')
    routed=until_ready(lambda:(v if(v:=stream())and v['sink']==neutral['index']else None),'stream returned to private neutral sink')
    evidence['routingReadbacks'].append(routed)
    for name in ['OpenAL Soft default HRTF.wav','Steam Audio.wav']:
        path=plugin/'hrir-audio'/name
        assert current('set_hrir_file',str(path))is True
        active=until_ready(sink,'preset reload')
        assert len(active['channel_map'])==(6 if name.startswith('OpenAL')else 8)
        evidence['presets'].append(dict(name=name,sink=active))
    # End only the exact owned filter; the backend's periodic check must recover it.
    filters={pid:info for pid,info in descendants(backend.pid).items()
             if Path('/proc',str(pid),'cmdline').read_bytes().startswith(b'pw-cli\0-m\0load-module\0')}
    assert len(filters)==1
    filter_pid,filter_identity=next(iter(filters.items()))
    os.kill(filter_pid,signal.SIGTERM)
    until_ready(lambda: (identity(filter_pid)is None),'owned filter exits')
    assert current('check_state')is None
    recovered=until_ready(sink,'owned filter recovered by actual backend check')
    evidence['filterRecovery']=dict(oldPid=filter_pid,oldIdentity=filter_identity,recoveredSink=recovered)
    assert current('run_sound_test','virtual-surround-sound')is True
    sound_channels={}
    def speakers():
        found=[]
        for pid,info in descendants(backend.pid).items():
            try:args=Path('/proc',str(pid),'cmdline').read_bytes().split(b'\0')
            except FileNotFoundError:continue
            if args[0]==b'speaker-test':
                args=[v.decode()for v in args if v]
                sound_channels[args[-1]]=dict(pid=pid,identity=info,args=args)
                found.append(pid)
        return found
    until_ready(lambda: speakers(),'owned sound-test subprocess')
    until_ready(lambda: (speakers()and len(sound_channels)>=2),'second sound-test channel',timeout=15)
    evidence['soundTestChannelsBeforeOwnedCancellation']=sound_channels
    assert current('set_hrir_file','/etc/passwd')is False
    assert current('enable_for_app','FrameySavedChoice')is True
    sibling=subprocess.Popen([sys.executable,'-c','import time; time.sleep(90)'],start_new_session=True)
    processes.append(sibling);sibling_identity=identity(sibling.pid)
    for cycle in range(2):
        if cycle==0:
            assert speakers(),'sound-test child must be active for unload proof'
        evidence['stops'].append(stop(backend,log))
        nodes=command(env,'pw-cli','ls','Node');assert '"input.virtual-surround-sound"'not in nodes
        sibling_after=identity(sibling.pid)
        assert sibling.poll()is None and sibling_after is not None
        assert (sibling_after['parent'],sibling_after['start'])==(sibling_identity['parent'],sibling_identity['start'])
        if cycle==0:
            backend=subprocess.Popen([str(loader)],env=env,stdout=log,stderr=log,start_new_session=True)
            processes.append(backend)
            until_ready(sink,'surround after loader restart')
            assert current('get_enabled_apps_list')==['FrameySavedChoice']
    evidence['unrelatedSiblingPreserved']=True
    after={p:dict(sha256=hashlib.sha256(Path(p).read_bytes()).hexdigest(),inode=Path(p).stat().st_ino,
                 mode=Path(p).stat().st_mode,mtimeNs=Path(p).stat().st_mtime_ns)for p in fixture['files']}
    assert after==fixture['files'];evidence['sharedFilesAfter']=after
    evidence['installedHashes']={p:hashlib.sha256((plugin/p).read_bytes()).hexdigest()
        for p in ['main.py','service.sh','py_modules/framey_surround.py','py_modules/framey_decky_ipc.py']}
    evidence['noUnmanagedServiceStopped']=True
    evidence['officialUiVerified']=False
    return evidence
