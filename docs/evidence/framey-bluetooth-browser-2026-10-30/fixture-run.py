import base64,hashlib,importlib.util,io,json,os,signal,subprocess,sys,tarfile,time
from pathlib import Path
ROOT=Path('/tmp/framey-bluetooth-private-bluez-mppkd9qczt');OWN=Path(__file__).parent
OUTPUT=Path(sys.argv[1]);assert not OUTPUT.exists();OUTPUT.mkdir()
sha=lambda x:hashlib.sha256(x).hexdigest()
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
packer=module('bluetooth_vm_packer',ROOT/'scripts/framey-test-syncthing-service.py')
codec=module('bluetooth_guest_codec',ROOT/'tests/decky-runtime/guest_result.py')
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();assert head=='6a2175e3f7fbfd1388db54a08a5942b0e7b5e4fd'
names=[str(p.relative_to(ROOT)) for p in (ROOT/'ui').glob('*') if p.is_file() and p.suffix in ('.py','.json','.html','.js')]
names+=['tests/decky-runtime/bluetooth_bluez.py','tests/fixtures/framey-bluez/service.py','ui/vendor/react-18.3.1.min.js','ui/vendor/react-dom-18.3.1.min.js','tests/fixtures/framey-official/18.zip']
raw=io.BytesIO();sources={}
with tarfile.open(fileobj=raw,mode='w') as t:
 for name in sorted(names):
  data=(ROOT/name).read_bytes();assert data==subprocess.check_output(['git','show',head+':'+name],cwd=ROOT)
  sources[name]=sha(data);entry=tarfile.TarInfo(name);entry.size=len(data);entry.mode=0o600;t.addfile(entry,io.BytesIO(data))
common=Path('/tmp/framey-terminal-browser-candidate-mppkd9qczt/tests/decky-runtime/terminal_browser.py').read_bytes()
probe=(OWN/'probe.py').read_bytes();compile(probe,'probe.py','exec')
BOOT=r'''
import hashlib,io,json,os,subprocess,sys,tarfile,traceback
from pathlib import Path
sys.path.insert(0,'/input')
from guest_result import write_result,PORT
assert os.getuid()==0 and Path('/framey-owned-vm').read_bytes()==b'Frame Control Flatpak VM v1\n'
report=dict(success=False,realFrameContacted=False)
try:
 inputs=json.loads(Path('/input/inputs.json').read_text());data=Path('/input/source.tar').read_bytes();assert hashlib.sha256(data).hexdigest()==inputs['sourceArchiveSha256']
 root=Path('/repo');root.mkdir(exist_ok=True);assert not any(root.iterdir())
 with tarfile.open(fileobj=io.BytesIO(data)) as t:
  assert set(t.getnames())==set(inputs['sourceSha256'])
  for entry in t:
   assert entry.isfile() and not entry.name.startswith('/') and '..' not in Path(entry.name).parts
   raw=t.extractfile(entry).read();assert hashlib.sha256(raw).hexdigest()==inputs['sourceSha256'][entry.name]
   p=root/entry.name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
 subprocess.run(['mount','-t','tmpfs','-o','size=768m,uid=1100,gid=1100,mode=700','tmpfs','/home/tester'],check=True,timeout=15)
 subprocess.run(['systemctl','start','user@1100.service'],check=True,timeout=40)
 p=subprocess.run(['unshare','--mount','--propagation','private','sh','-c','mount -t tmpfs -o mode=755 tmpfs /run/dbus && exec "$@"','framey-private-bluez','runuser','-u','tester','--','env','HOME=/home/tester','PYTHONDONTWRITEBYTECODE=1','PYTHONUNBUFFERED=1','XDG_RUNTIME_DIR=/run/user/1100','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1100/bus','python3','/input/probe.py'],capture_output=True,text=True,timeout=400)
 report['exitStatus']=p.returncode;report['stdoutTail']=p.stdout[-4000:];report['stderrTail']=p.stderr[-12000:]
 result=Path('/home/tester/bluetooth-browser-result.json')
 if result.is_file():report['browser']=json.loads(result.read_bytes())
 assert p.returncode==0 and report.get('browser',{}).get('success'),report.get('browser',{}).get('error','probe failed')
 report['success']=True
except BaseException as e:report['error']=str(e);report['traceback']=traceback.format_exc()
finally:
 p=subprocess.run(['systemctl','stop','user@1100.service'],capture_output=True,text=True,timeout=40);report['ownedUserManagerStopped']=p.returncode==0
 if p.returncode:report['success']=False
 ports=[p for p in Path('/sys/class/virtio-ports').glob('vport*p*/name') if p.read_text().strip()==PORT];assert len(ports)==1
 with Path('/dev',ports[0].parent.name).open('wb',buffering=0) as f:write_result(f,report)
 subprocess.run(['systemd-run','--unit=framey-bluetooth-shutdown','--on-active=2','--timer-property=AccuracySec=100ms','/usr/bin/systemctl','poweroff'],check=True,timeout=15)
'''
rootfs=Path('/tmp/framey-syncthing-browser-rootfs-mppkd9qczt.tar');loader=Path('/tmp/framey-syncthing-runtime-mppkd9qczt/PluginLoader').read_bytes();assert sha(loader)=='e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181'
inputs=dict(sourceRevision=head,sourceSha256=sources,sourceArchiveSha256=sha(raw.getvalue()),auxiliarySourceSha256={'probe.py':sha(probe),'browser_common.py':sha(common),'guest_result.py':sha((ROOT/'tests/decky-runtime/guest_result.py').read_bytes()),'bootstrap':sha(BOOT.encode()),'runner':sha(Path(__file__).read_bytes())},rootfsSha256=hashlib.file_digest(rootfs.open('rb'),'sha256').hexdigest(),loaderSha256=sha(loader),realFrameContacted=False,networkDevice=False,hostBusExposed=False,architecture=os.uname().machine,privateTestBridge=True,productionHttpParentVerified=False)
(OUTPUT/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
kernel=packer.pack(rootfs,OUTPUT/'initrd.gz',{'PluginLoader':loader,'source.tar':raw.getvalue(),'probe.py':probe,'browser_common.py':common,'guest_result.py':(ROOT/'tests/decky-runtime/guest_result.py').read_bytes(),'inputs.json':json.dumps(inputs).encode()},marker=b'Frame Control Flatpak VM v1\n',bootstrap=BOOT.encode(),user_probe=b'# unused\n',normal_root=True,timeout=480,root_size_mib=3072,browser=True)
(OUTPUT/'vmlinuz').write_bytes(kernel)
packet=OUTPUT/'guest-result.packet';command=['qemu-system-x86_64','-accel','tcg,thread=multi','-cpu','max','-smp','2','-m','6144','-nodefaults','-nographic','-serial','stdio','-monitor','none','-no-reboot','-nic','none','-kernel',str(OUTPUT/'vmlinuz'),'-initrd',str(OUTPUT/'initrd.gz'),'-append','console=ttyS0 rdinit=/init panic=-1 quiet','-chardev','file,id=framey_result,path='+str(packet),'-device','virtio-serial-pci,id=framey_result_bus','-device','virtserialport,bus=framey_result_bus.0,chardev=framey_result,name='+codec.PORT]
report=dict(success=False,inputs=inputs,ownedQemuReaped=False);p=None
try:
 with (OUTPUT/'console.log').open('wb') as log:
  p=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);report['qemuPid']=p.pid;assert p.wait(timeout=540)==0
 report['guest']=codec.decode(packet.read_bytes());report['guestPacketSha256']=sha(packet.read_bytes());report['success']=report['guest']['success']
 if 'browser'in report['guest']:
  for name,data in report['guest']['browser']['screenshots'].items():(OUTPUT/(name+'.png')).write_bytes(base64.b64decode(data,validate=True))
finally:
 if p is not None:
  if p.poll()is None:
   os.killpg(p.pid,signal.SIGTERM)
   try:p.wait(timeout=8)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait(timeout=8)
  report['ownedQemuReaped']=p.poll()is not None
 (OUTPUT/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('success','ownedQemuReaped')}),flush=True)
 if report.get('guest',{}).get('error'):print(report['guest']['error'])
 if not report['success']:sys.exit(1)
