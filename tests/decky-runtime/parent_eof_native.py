"""Disposable published-loader experiment. No host or headset contact."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import time
import traceback

sys.path.insert(0, '/repo/tests/decky-runtime')
from check import rpc, until_ready
from deck_settings_private import identity, descendants

home = Path.home()
base = home/'.local/share/frame-control/decky'
plugin = base/'plugins/owned-parent-eof-probe'
plugin.mkdir(parents=True)
(plugin/'py_modules').mkdir()
shutil.copy('/repo/ui/framey_decky_ipc.py', plugin/'py_modules/framey_decky_ipc.py')
(plugin/'plugin.json').write_text(json.dumps(dict(name='Owned EOF Probe', author='Frame Control', flags=[], api_version=1)))
(plugin/'package.json').write_text(json.dumps(dict(name='owned-parent-eof-probe', version='0.0.0')))
(plugin/'main.py').write_text('''from framey_decky_ipc import install
install()
import os
class Plugin:
    async def ping(self):
        return {"pid": os.getpid(), "value": "owned-pong"}
    async def _main(self):
        pass
    async def _unload(self):
        pass
''')
(home/'.local/share/Steam/steamui/images').mkdir(parents=True)
loader = base/'PluginLoader'
shutil.copy('/input/PluginLoader', loader)
loader.chmod(0o700)
env = dict(os.environ, UNPRIVILEGED_PATH=str(base), PRIVILEGED_PATH=str(base), CHOWN_PLUGIN_PATH='0',
           LIVE_RELOAD='0', USE_CEF_CLOSE_WORKAROUND='0', KEEP_SYSTEMD_SERVICE='1',
           DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1100/bus')
report = dict(architecture=platform.machine(), loaderSha256=hashlib.sha256(loader.read_bytes()).hexdigest(),
              syntheticPlugin=True, childEofRepairPresent=True, parentUnmodified=True,
              realFrameContacted=False, nativeArm64Executed=platform.machine() == 'aarch64', historicalArm64VmExecuted=False,
              historicalCauseEstablished=False, releaseHoldCleared=False, results=[])

def cpu(pid):
    return [int(v) for v in (Path('/proc')/str(pid)/'stat').read_text().rsplit(')', 1)[1].split()[11:13]]

def same(pid, old):
    state = identity(pid)
    return state and state['start'] == old['start']

def reap(recorded, timeout=2):
    deadline = time.monotonic()+timeout
    while True:
        for pid, old in recorded.items():
            if same(pid, old):
                try:
                    os.waitpid(pid, os.WNOHANG)
                except ChildProcessError:
                    pass
        left = {pid: identity(pid) for pid, old in recorded.items() if same(pid, old)}
        if not left or time.monotonic() >= deadline:
            return left
        time.sleep(.02)

try:
    pins = {'x86_64': 'e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181', 'aarch64': '8ef5dcf36cbbbb6e97201a6baed5d79c4cc44ec27789fc9af1c5b6ae8f0b25b6'}
    assert report['loaderSha256'] == pins[platform.machine()]
    for mode in ['normal', 'abrupt-child-exit']:
        item = dict(mode=mode)
        report['results'].append(item)
        logpath = home/(mode+'.log')
        with logpath.open('w+') as log:
            backend = subprocess.Popen([str(loader)], env=env, stdout=log, stderr=log, start_new_session=True)
            recorded = {}
            try:
                item['plugins'] = until_ready(lambda: rpc('loader/get_plugins'), 'synthetic plugin discovery')
                ping = until_ready(lambda: rpc('loader/call_plugin_method', 'Owned EOF Probe', 'ping'), 'synthetic plugin RPC')
                assert ping['value'] == 'owned-pong', ping
                recorded = descendants(backend.pid)
                item.update(loaderPid=backend.pid, pluginPid=ping['pid'], descendantsBefore=recorded)
                assert ping['pid'] in recorded
                cpus = {pid: cpu(pid) for pid in recorded}
                if mode == 'abrupt-child-exit':
                    assert same(ping['pid'], recorded[ping['pid']])
                    os.kill(ping['pid'], signal.SIGKILL)
                    # Ask another owned Python process so its wall-clock deadline
                    # cannot be starved by a stuck loader event loop.
                    code = "import sys;sys.path.insert(0,'/repo/tests/decky-runtime');from check import rpc;print(rpc('loader/get_plugins'))"
                    started = time.monotonic()
                    try:
                        read = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=5)
                        item['responseAfterEof'] = dict(wallDeadlineExceeded=False, requestTimedOut=read.returncode != 0 and read.stderr.rstrip().endswith('TimeoutError: timed out'), returncode=read.returncode, stdout=read.stdout, stderr=read.stderr)
                    except subprocess.TimeoutExpired:
                        item['responseAfterEof'] = dict(wallDeadlineExceeded=True, requestTimedOut=True)
                    item['responseSeconds'] = round(time.monotonic()-started, 3)
                item['cpuTickDeltas'] = {pid: [a-b for a,b in zip(cpu(pid), old)] for pid, old in cpus.items() if same(pid, recorded[pid])}
                started = time.monotonic()
                backend.send_signal(signal.SIGTERM)
                try:
                    backend.wait(timeout=8)
                    item['parentTermTimedOut'] = False
                except subprocess.TimeoutExpired:
                    item['parentTermTimedOut'] = True
                item.update(parentTermSeconds=round(time.monotonic()-started, 3), loaderReturncode=backend.poll())
            finally:
                # Track exact owned descendants before reaping any orphan.
                recorded.update(descendants(backend.pid))
                item['remainingBeforeCleanup'] = reap(recorded, timeout=.2)
                item['forcedCleanupPids'] = []
                for pid, old in recorded.items():
                    if same(pid, old):
                        os.kill(pid, signal.SIGKILL)
                        item['forcedCleanupPids'].append(pid)
                if backend.poll() is None:
                    backend.kill()
                backend.wait(timeout=3)
                item['remainingAfterCleanup'] = reap(recorded)
                item['console'] = logpath.read_text()
                item['consoleSha256'] = hashlib.sha256(item['console'].encode()).hexdigest()
        print('PROBE_CASE '+json.dumps(item), flush=True)
    normal, abrupt = report['results']
    report['normalControlPassed'] = (not normal['parentTermTimedOut'] and normal['loaderReturncode'] == 0 and not normal['forcedCleanupPids'])
    report['publishedBinaryParentHangReproduced'] = (report['normalControlPassed'] and abrupt['parentTermTimedOut'] and abrupt['responseAfterEof']['requestTimedOut'])
    report['allOwnedProcessesReaped'] = all(not x['remainingAfterCleanup'] for x in report['results'])
except BaseException:
    report['error'] = traceback.format_exc()
finally:
    print('PROBE_REPORT '+json.dumps(report), flush=True)
