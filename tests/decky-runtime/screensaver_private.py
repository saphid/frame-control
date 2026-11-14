"""Real private D-Bus clients and name ownership; never host inhibit services."""
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

NAMES = ('org.freedesktop.PowerManagement', 'org.freedesktop.ScreenSaver', 'org.gnome.SessionManager')
SERVICES = (
    (NAMES[1], '/org/freedesktop/ScreenSaver', 'org.freedesktop.ScreenSaver', 'UnInhibit'),
    (NAMES[0], '/org/freedesktop/PowerManagement/Inhibit', 'org.freedesktop.PowerManagement.Inhibit', 'UnInhibit'),
    (NAMES[2], '/org/gnome/SessionManager', 'org.gnome.SessionManager', 'Uninhibit'),
)


class Oracle:
    def __init__(self, address):
        import dbus
        self.dbus=dbus;self.address=address;self.calls=[]
        self.client=dbus.bus.BusConnection(address)
        self.sibling='org.framecontrol.PrivateScreenSaverFixture'
        assert self.client.request_name(self.sibling,dbus.bus.NAME_FLAG_DO_NOT_QUEUE)==1
        self.sibling_owner=str(self.client.get_unique_name())
        self.blocker=dbus.bus.BusConnection(address)
        assert self.blocker.request_name(NAMES[1],dbus.bus.NAME_FLAG_DO_NOT_QUEUE)==1
        self.blocker_owner=str(self.blocker.get_unique_name())

    def owner(self, name):
        return str(self.client.get_name_owner(name)) if self.client.name_has_owner(name) else None

    def call(self, service, method, args, signature, *, client=None, path=None):
        name,default_path,interface,_=SERVICES[service]
        peer=client if client is not None else self.client
        target=peer.get_object(name,path or default_path,introspect=False)
        response=target.get_dbus_method(method,interface)(*args,signature=signature,timeout=3)
        value=int(response) if response is not None else None
        self.calls.append(dict(name=name,path=path or default_path,interface=interface,method=method,
            args=list(args),signature=signature,result=value,client=str(peer.get_unique_name())))
        return value

    def inhibit(self, service, app='Private player', *, client=None, path=None):
        args=[app,'Private playback'] if service!=2 else [app,self.dbus.UInt32(0),'Private playback',self.dbus.UInt32(8)]
        return self.call(service,'Inhibit',args,'ss'if service!=2 else'susu',client=client,path=path)

    def uninhibit(self, service, cookie):
        self.call(service,SERVICES[service][3],[self.dbus.UInt32(cookie)],'u')

    def close(self):
        self.blocker.close();self.client.close()


def start(env, log, processes, until_ready):
    assert env['DBUS_SESSION_BUS_ADDRESS']=='unix:path=/run/user/1100/bus'
    daemon=subprocess.Popen(['dbus-daemon','--session','--nofork',
        '--address='+env['DBUS_SESSION_BUS_ADDRESS']],env=env,stdout=log,stderr=log,start_new_session=True)
    processes.append(daemon)
    until_ready(lambda:Path('/run/user/1100/bus').is_socket(),'private screensaver bus')
    return Oracle(env['DBUS_SESSION_BUS_ADDRESS'])


def stop(backend, log, disconnect):
    before=descendants(backend.pid);assert before
    peers=[]
    if disconnect:
        paths=list(Path('/tmp').glob('plugin_socket_*'));assert len(paths)==1
        with socket.socket(socket.AF_UNIX)as peer:
            peer.settimeout(.2);peer.connect(str(paths[0]));peer.shutdown(socket.SHUT_WR)
        peers=[str(paths[0])];time.sleep(.05)
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
    assert 'Plugin ScreenSaver (v1.1.2) has been stopped in 'in console and console.count('Goodnight World!')==1
    return dict(parentOnlySignal=True,returncode=backend.returncode,seconds=seconds,
        descendantsBefore=before,exactDescendantsRemaining=remaining,adoptedChildExits=adopted,
        closedUnixPeers=peers,console=console,consoleSha256=hashlib.sha256(console.encode()).hexdigest(),cleanShutdownVerified=True)


def probe(backend, loader, env, log, processes, legacy, rpc, until_ready, oracle, plugin, discovered):
    evidence=dict(busAddress=oracle.address,names=list(NAMES),initialExistingOwner=oracle.blocker_owner,
        stops=[],owners=[],events=[],privateWireCalls=oracle.calls,realFrameContacted=False,
        hostBusExposed=False,actualSuspendInhibitionVerified=False,officialUiVerified=False)
    sibling=subprocess.Popen([sys.executable,'-c','import time; time.sleep(100)'],start_new_session=True)
    processes.append(sibling);sibling_before=identity(sibling.pid)
    marker=Path.home()/'private-unrelated-screen-marker';marker.write_bytes(b'private unrelated marker')
    snapshot=lambda p:dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),inode=p.stat().st_ino,mode=p.stat().st_mode,mtimeNs=p.stat().st_mtime_ns)
    initial_marker=snapshot(marker)
    def events(expected):
        actual=legacy('get_event');assert actual==expected,actual;evidence['events'].append(actual)
    def owners():return [oracle.owner(name)for name in NAMES]
    try:
        assert legacy('is_running')is False
        assert legacy('start_backend')is False,'must refuse an existing private desktop service'
        assert legacy('is_running')is False
        assert owners()==[None,oracle.blocker_owner,None]
        core=oracle.client.get_object('org.freedesktop.DBus','/org/freedesktop/DBus',introspect=False)
        queued=core.get_dbus_method('ListQueuedOwners','org.freedesktop.DBus')(NAMES[1],signature='s',timeout=3)
        assert list(map(str,queued))==[oracle.blocker_owner]
        evidence['busyNamesPreservedWithoutQueue']=owners()
        assert oracle.blocker.release_name(NAMES[1])==1
        until_ready(lambda:all(v is None for v in owners()),'no delayed queued ownership')
        assert legacy('start_backend')is True
        owned=owners();assert len(set(owned))==1 and owned[0]not in(None,oracle.blocker_owner,oracle.sibling_owner)
        evidence['owners'].append(owned)
        assert legacy('is_running')is True
        for app in ['Steam','./steamwebhelper']:assert oracle.inhibit(0,app)==0
        events([])
        cookies=[oracle.inhibit(i)for i in range(3)]
        assert len(set(cookies))==3 and all(v>0 for v in cookies)
        events([dict(type='Inhibit')]*3)
        for i,cookie in enumerate(cookies):
            oracle.uninhibit(i,cookie);events([dict(type='UnInhibit')]if i==2 else[])
        alias=oracle.inhibit(0,path='/ScreenSaver');assert alias>0;events([dict(type='Inhibit')])
        oracle.uninhibit(0,alias);events([dict(type='UnInhibit')])
        orphan=oracle.dbus.bus.BusConnection(oracle.address)
        assert oracle.inhibit(0,client=orphan)>0;events([dict(type='Inhibit')]);orphan.close()
        until_ready(lambda:legacy('get_event')==[dict(type='UnInhibit')],'actual disconnected inhibitor peer release')
        evidence['disconnectedInhibitorReleased']=True
        legacy('set_settings',key='private_label',value='Private playback')
        legacy('set_settings',key='private_false',value=False)
        assert legacy('get_settings',key='private_label',defaults=None)=='Private playback'
        assert legacy('get_settings',key='private_false',defaults=True)is False
        assert oracle.inhibit(0)>0;events([dict(type='Inhibit')])
        legacy('stop_backend');assert legacy('is_running')is False;assert owners()==[None]*3;events([])
        assert legacy('start_backend')is True;events([])
        assert oracle.inhibit(1)>0;events([dict(type='Inhibit')])
        evidence['stops'].append(stop(backend,log,True));assert owners()==[None]*3
        assert oracle.owner(oracle.sibling)==oracle.sibling_owner
        candidates=list(Path.home().rglob('settings.json'));assert len(candidates)==1,candidates
        settings=candidates[0];evidence['actualUserSettingsPath']=str(settings)
        stored=json.loads(settings.read_text());assert stored['private_label']=='Private playback'and stored['private_false']is False
        evidence['settingsBeforeRestart']=snapshot(settings)
        backend=subprocess.Popen([str(loader)],env=env,stdout=log,stderr=log,start_new_session=True);processes.append(backend)
        found=until_ready(lambda:rpc('loader/get_plugins'),'restarted screensaver discovery');assert found==discovered
        assert legacy('is_running')is False;events([])
        assert legacy('get_settings',key='private_label',defaults=None)=='Private playback'
        assert legacy('get_settings',key='private_false',defaults=True)is False
        assert legacy('start_backend')is True
        restarted=owners();assert len(set(restarted))==1 and restarted[0]not in owned+[None]
        evidence['owners'].append(restarted)
        assert oracle.inhibit(2)>0;events([dict(type='Inhibit')])
        evidence['stops'].append(stop(backend,log,False));assert owners()==[None]*3
        evidence['settingsAfterRestart']=snapshot(settings);assert evidence['settingsAfterRestart']==evidence['settingsBeforeRestart']
        state=identity(sibling.pid);assert sibling.poll()is None and state['parent']==sibling_before['parent']and state['start']==sibling_before['start']
        assert oracle.owner(oracle.sibling)==oracle.sibling_owner
        evidence['unrelatedSiblingAndBusNamePreserved']=True
        evidence['unrelatedMarkerBefore']=initial_marker;evidence['unrelatedMarkerAfter']=snapshot(marker)
        assert evidence['unrelatedMarkerAfter']==initial_marker
        evidence['installedHashes']={p:hashlib.sha256((plugin/p).read_bytes()).hexdigest()for p in ['main.py','py_modules/framey_screensaver.py','py_modules/framey_decky_ipc.py']}
        return evidence
    finally:
        oracle.close()
        if sibling.poll()is None:sibling.terminate()
        sibling.wait(timeout=3)
