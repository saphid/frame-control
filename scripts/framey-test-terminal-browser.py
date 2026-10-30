#!/usr/bin/env python3
"""Private AMD64 Terminal browser experiment in a networkless disposable VM.

Requires an existing browser rootfs and exact cached published Decky loader.
No production adapter, host/session mounts, network NIC or Frame is used.
"""
import argparse
import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import tarfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MARKER = b'Frame Control Flatpak VM v1\n'
BOOTSTRAP = r'''
import hashlib, io, json, os, subprocess, sys, tarfile, traceback
from pathlib import Path
assert os.getuid()==0 and os.getpid()!=1
assert Path('/framey-owned-vm').read_bytes()==b'Frame Control Flatpak VM v1\n'
assert Path('/proc/1/comm').read_text().strip()=='systemd'
assert not Path('/sys/class/net/eth0').exists()
sys.path.insert(0,'/input')
from guest_result import write_result, PORT
report=dict(success=False,realFrameContacted=False,networkDevice=False,hostBusExposed=False)
try:
 inputs=json.loads(Path('/input/terminal-inputs.json').read_text())
 raw=Path('/input/terminal-source.tar').read_bytes()
 assert hashlib.sha256(raw).hexdigest()==inputs['sourceArchiveSha256']
 root=Path('/repo');root.mkdir(exist_ok=True)
 assert root.is_dir() and not root.is_symlink() and not any(root.iterdir()), 'Only an empty owned guest repo may receive source'
 with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
  assert set(archive.getnames())==set(inputs['sourceSha256'])
  for member in archive:
   assert member.isfile() and not member.name.startswith('/') and '..' not in Path(member.name).parts
   assert 0<=member.size<=32*1024*1024
   data=archive.extractfile(member).read()
   assert hashlib.sha256(data).hexdigest()==inputs['sourceSha256'][member.name]
   target=root/member.name;target.parent.mkdir(parents=True,exist_ok=True)
   target.write_bytes(data);target.chmod(member.mode&0o755)
 subprocess.run(['mount','-t','tmpfs','-o','size=768m,uid=1100,gid=1100,mode=700','tmpfs','/home/tester'],check=True,timeout=15)
 subprocess.run(['systemctl','start','user@1100.service'],check=True,timeout=40)
 command=['runuser','-u','tester','--','env','HOME=/home/tester','PYTHONDONTWRITEBYTECODE=1','PYTHONUNBUFFERED=1','XDG_RUNTIME_DIR=/run/user/1100','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1100/bus','python3','/repo/tests/decky-runtime/check.py','65','-','--terminal-candidate','--terminal-browser-candidate']
 result=subprocess.run(command,capture_output=True,text=True,timeout=360)
 report['probeExitStatus']=result.returncode
 lines=result.stdout.splitlines()
 report['stdoutTail']=result.stdout[-24000:]
 report['stderrTail']=result.stderr[-32000:]
 partial=[line.split('FRAMEY_TERMINAL_BROWSER_JSON=',1)[1] for line in result.stderr.splitlines() if 'FRAMEY_TERMINAL_BROWSER_JSON=' in line]
 if partial:report['partialBrowser']=json.loads(partial[-1])
 assert result.returncode==0 and len(lines)==1, 'Owned Terminal probe failed, exit '+str(result.returncode)
 report['terminal']=json.loads(lines[0])
 assert report['terminal']['terminalBrowser']['success'] is True
 report['success']=True
except BaseException as error:
 report['error']=str(error)[:2000];traceback.print_exc()
finally:
 result=subprocess.run(['systemctl','stop','user@1100.service'],capture_output=True,text=True,timeout=40)
 report['ownedUserManagerStopped']=result.returncode==0
 if result.returncode:report['success']=False
 ports=[p for p in Path('/sys/class/virtio-ports').glob('vport*p*/name') if p.read_text().strip()==PORT]
 assert len(ports)==1
 with Path('/dev',ports[0].parent.name).open('wb',buffering=0) as stream:write_result(stream,report)
 subprocess.run(['systemd-run','--unit=framey-terminal-shutdown','--on-active=2','--timer-property=AccuracySec=100ms','/usr/bin/systemctl','poweroff'],check=True,timeout=15)
'''


def module(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rootfs-tar',type=Path,required=True)
    parser.add_argument('--loader',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    assert sys.platform=='linux' and platform.machine()=='x86_64'
    assert not args.output.exists(), 'Use a new owned evidence directory'
    names=subprocess.check_output(['git','ls-files','ui'],cwd=ROOT,text=True).splitlines()
    names += ['tests/framey_official.py','tests/fixtures/framey-official/65.zip',
              'tests/decky-runtime/check.py','tests/decky-runtime/cases.json',
              'tests/decky-runtime/terminal_lifecycle.py','tests/decky-runtime/terminal_candidate.py','tests/decky-runtime/timer_lifecycle.py',
              'tests/decky-runtime/terminal_browser.py','tests/decky-runtime/guest_result.py',
              'scripts/framey-test-terminal-browser.py','scripts/framey-test-syncthing-service.py']
    names += subprocess.check_output(['git','ls-files','tests/fixtures/framey-terminal-python314-amd'],cwd=ROOT,text=True).splitlines()
    names=sorted(set(names))
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    sources={}
    raw=io.BytesIO()
    with tarfile.open(fileobj=raw,mode='w') as archive:
        for name in names:
            path=ROOT/name;assert path.is_file() and not path.is_symlink()
            data=path.read_bytes()
            assert data==subprocess.check_output(['git','show',head+':'+name],cwd=ROOT), name
            assert len(data)<=32*1024*1024
            if name.endswith('.py'):
                compile(data, name, 'exec')
            sources[name]=digest(data)
            member=tarfile.TarInfo(name);member.mode=path.stat().st_mode&0o755;member.size=len(data)
            archive.addfile(member,io.BytesIO(data))
    loader=args.loader.read_bytes()
    assert digest(loader)=='e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181'
    sys.path[:0]=[str(ROOT/'ui'),str(ROOT/'tests')]
    import framey_panel,framey_official
    record=next(p for p in framey_official.PLUGINS if p['id']==65)
    official=framey_official.archive(record)
    assert digest(official)==record['sha256']
    import zipfile
    with zipfile.ZipFile(io.BytesIO(official)) as archive:
        frontend=archive.read(record['folder']+'/dist/index.js')
    with patch.object(framey_panel,'_owned_dist',return_value=(None,frontend,record['sha256'])):
        panel=framey_panel.panel(65).decode()
    for route,name in [('react.js','vendor/react-18.3.1.min.js'),('react-dom.js','vendor/react-dom-18.3.1.min.js'),('host.js','framey-host.js')]:
        encoded=base64.b64encode((ROOT/'ui'/name).read_bytes()).decode()
        panel=panel.replace('src="/framey-runtime/'+route+'"','src="data:text/javascript;base64,'+encoded+'"')
    assert '/framey-runtime/' not in panel
    codec=module('terminal_result_codec',ROOT/'tests/decky-runtime/guest_result.py')
    packer=module('terminal_vm_packer',ROOT/'scripts/framey-test-syncthing-service.py')
    inputs=dict(sourceRevision=head,sourceSha256=sources,sourceArchiveSha256=digest(raw.getvalue()),
        loaderSha256=digest(loader),officialArchiveSha256=digest(official),frontendSha256=digest(frontend),
        panelSha256=digest(panel.encode()),bootstrapSha256=digest(BOOTSTRAP.encode()),
        rootfsSha256=hashlib.file_digest(args.rootfs_tar.open('rb'),'sha256').hexdigest(),
        architecture='x86_64',cpuModel='max',accelerator='tcg,thread=multi',
        memoryMiB=6144,timeoutSeconds=480,
        networkDevice=False,hostBusExposed=False,realFrameContacted=False,productionAdaptationEnabled=False,
        resultTransport=dict(kind='virtio-serial',port=codec.PORT,maximumPayloadBytes=codec.MAX_PAYLOAD))
    args.output.mkdir(parents=True)
    (args.output/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
    kernel=packer.pack(args.rootfs_tar,args.output/'initrd.gz',{
        'PluginLoader':loader,'terminal-source.tar':raw.getvalue(),'terminal-panel.html':panel.encode(),
        'terminal-inputs.json':json.dumps(inputs).encode(),'guest_result.py':(ROOT/'tests/decky-runtime/guest_result.py').read_bytes()},
        marker=MARKER,bootstrap=BOOTSTRAP.encode(),user_probe=b'# not used\n',
        normal_root=True,timeout=440,root_size_mib=3072,browser=True)
    (args.output/'vmlinuz').write_bytes(kernel)
    packet=args.output/'guest-result.packet'
    command=['qemu-system-x86_64','-accel',inputs['accelerator'],'-cpu',inputs['cpuModel'],
        '-smp','2','-m','6144','-nographic','-monitor','none','-no-reboot',
        '-nic','none','-kernel',str(args.output/'vmlinuz'),'-initrd',str(args.output/'initrd.gz'),
        '-append','console=ttyS0 rdinit=/init panic=-1 quiet',
        '-chardev','file,id=framey_result,path='+str(packet).replace(',',',,'),
        '-device','virtio-serial-pci,id=framey_result_bus',
        '-device','virtserialport,bus=framey_result_bus.0,chardev=framey_result,name='+codec.PORT]
    report=dict(success=False,inputs=inputs,ownedQemuReaped=False)
    process=None
    try:
        with (args.output/'console.log').open('wb') as log:
            process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            assert process.wait(timeout=480)==0
        guest=codec.decode(packet.read_bytes());report['guest']=guest
        assert guest['success'] is True, guest.get('error','Private Terminal runtime failed')
        assert guest['ownedUserManagerStopped'] is True
        report['success']=True
    finally:
        if process is not None:
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGTERM)
                try:process.wait(timeout=8)
                except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=8)
            report['ownedQemuReaped']=process.poll() is not None
        (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(dict(success=report['success'],ownedQemuReaped=report['ownedQemuReaped'],output=str(args.output))),flush=True)


if __name__=='__main__':
    main()
