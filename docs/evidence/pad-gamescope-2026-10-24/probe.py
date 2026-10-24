"""Active real-Frame evidence probe: aborts unless idle, then owns the shared lock.

Run manually on an authorised host: python3 docs/evidence/pad-gamescope-2026-10-24/probe.py
The recorded run used /tmp paths; archived paths are relative to this checkout.
"""
import base64
import datetime
import json
import os
from pathlib import Path
import queue
import shlex
import subprocess
import sys
import tempfile
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
data = tempfile.TemporaryDirectory(prefix='pr66-live-')
os.environ.update(FRAME_CONTROL_DATA_DIR=data.name, FRAME_CONTROL_TELEMETRY='0', FRAME_PRIVATE_SSH='1')
sys.path.insert(0, str(ROOT / 'ui'))
import server

SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', 'frame']
owner = 'pr66-' + uuid.uuid4().hex
result = {'time': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'owner': owner,
          'base': '0da1fe5', 'route': 'production server.remote_input -> TouchAgent SSH -> frame_touch.py -> gamescope EIS',
          'events': []}
recorder = None
locked = False
rows = queue.Queue()

def ssh(cmd):
    return subprocess.run([*SSH, cmd], capture_output=True, text=True, timeout=15, check=True).stdout

def focus():
    return json.loads(server.ssh('python3 - focus', stdin=(ROOT/'ui/frame_touch.py').read_text(), timeout=15))

def activity():
    return json.loads(ssh('/opt/steamvr/bin/linuxarm64/vrcmd --stats'))[0]['activity_level']

def read_rows():
    for raw in recorder.stdout:
        rows.put(json.loads(raw))

def collect(seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            result['events'].append(rows.get(timeout=max(0.01, end-time.monotonic())))
        except queue.Empty:
            break

try:
    result['initial_focus'] = focus()
    result['initial_activity'] = activity()
    assert not result['initial_focus'].get('window'), 'existing focused panel; do not interrupt'
    assert result['initial_activity'] == 3, 'headset is not in standby'
    ssh('mkdir /tmp/frame-test.lock && printf %s ' + shlex.quote(owner) + ' > /tmp/frame-test.lock/owner')
    locked = True
    result['lock_acquired'] = True
    assert not focus().get('window') and activity() == 3, 'session changed during lock acquisition'
    code = base64.b64encode(Path(__file__).with_name('recorder.py').read_bytes()).decode()
    command = 'python3 -u -c ' + shlex.quote("import base64;exec(compile(base64.b64decode('" + code + "'),'pr66-recorder','exec'))")
    recorder = subprocess.Popen([*SSH, command], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
    threading.Thread(target=read_rows, daemon=True).start()
    initial = rows.get(timeout=8)
    result['recorder'] = initial
    assert initial.get('ready'), initial
    window = initial['window']
    for _ in range(20):
        current = focus()
        if current.get('window') == window:
            break
        time.sleep(0.2)
    result['focused_panel'] = current
    assert current.get('window') == window and current.get('display') == ':0', 'owned panel did not obtain focus; no input sent'
    server.remote_input({})
    for _ in range(50):
        if server._touch.status.get('state') in ('ready', 'error'):
            break
        time.sleep(0.1)
    result['agent_status'] = dict(server._touch.status)
    assert result['agent_status'].get('state') == 'ready', result['agent_status']
    target = {'window': window, 'display': ':0'}
    assert focus().get('window') == window and activity() == 3
    result['position_response'] = server.remote_touch({'events': [dict(target, fx=0.5, fy=0.5)]})
    time.sleep(0.2)
    assert focus().get('window') == window and activity() == 3
    result['pad_response'] = server.remote_input({'events': [{'singleclick': True}, {'key': 'Frame66'}, {'specialKey': 12}]})
    collect(2)
    received = result['events']
    result['received_text'] = ''.join(e.get('text', '') for e in received if e.get('type') == 2)
    result['click_received'] = any(e.get('type') == 4 and e.get('code') == 1 and e.get('window') == window for e in received)
    result['release_received'] = any(e.get('type') == 5 and e.get('code') == 1 and e.get('window') == window for e in received)
    result['passed'] = result['click_received'] and result['release_received'] and result['received_text'] == 'Frame66\r'
    assert result['passed'], 'event recorder did not observe expected click and keys'
except Exception as e:
    result['error'] = str(e)
finally:
    proc = server._touch.proc
    server.reset_pad_route()
    if proc:
        try:
            proc.wait(timeout=8)
            result['input_helper_exited'] = True
        except subprocess.TimeoutExpired:
            proc.terminate()
            proc.wait(timeout=5)
            result['input_helper_terminated'] = True
    if recorder:
        recorder.stdin.close()
        recorder.wait(timeout=8)
        collect(0.2)
        result['recorder_exit'] = recorder.returncode
        result['recorder_stderr'] = recorder.stderr.read()[-1000:]
    if locked:
        result['final_focus'] = focus()
        result['final_activity'] = activity()
        ssh('test "$(cat /tmp/frame-test.lock/owner)" = ' + shlex.quote(owner)
            + ' && rm /tmp/frame-test.lock/owner && rmdir /tmp/frame-test.lock')
        result['owned_lock_released'] = True
    Path('/tmp/pr66-live.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    data.cleanup()
sys.exit(0 if result.get('passed') else 1)
