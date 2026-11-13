"""On-demand, read-only Windows PC wireless inventory. Never contacts a headset.

PnP identity is evidence, not permission to disable a device. Multiple Wi-Fi
Direct instances are normal on some PCs; neither their suffix nor link state
identifies an unused instance or proves which radio belongs to Steam.
"""
import base64
import json
import os
import re
import subprocess
import threading
from datetime import datetime, timezone

import frame_host

TIMEOUT = 20
_lock = threading.Lock()

# Static queries only. No user values, execution-policy override, elevation,
# scans, network traffic, or settings changes. Do not return raw netsh output:
# it can contain SSIDs, MACs and location-permission instructions.
PROBE = r"""
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$r = @{pnp=@(); present=@(); adapters=@(); routes=@(); wlan=''; sources=@{}}
try {
  $r.pnp = @(Get-PnpDevice -Class Net | Select-Object InstanceId,FriendlyName,Status,Problem)
  $r.sources.pnp = 'ok'
} catch { $r.sources.pnp = 'unavailable' }
try {
  $r.present = @(Get-PnpDevice -Class Net -PresentOnly | ForEach-Object { $_.InstanceId })
  $r.sources.present = 'ok'
} catch { $r.sources.present = 'unavailable' }
try {
  $r.adapters = @(Get-NetAdapter -IncludeHidden | Select-Object PnPDeviceID,Name,InterfaceDescription,
    InterfaceGuid,ifIndex,InterfaceOperationalStatus,MediaConnectState,NdisPhysicalMedium,HardwareInterface)
  $r.sources.adapters = 'ok'
} catch { $r.sources.adapters = 'unavailable' }
try {
  $r.routes = @(Get-NetRoute | Where-Object {
    $_.DestinationPrefix -eq '0.0.0.0/0' -or $_.DestinationPrefix -eq '::/0'
  } | Select-Object InterfaceIndex)
  $r.sources.routes = 'ok'
} catch { $r.sources.routes = 'unavailable' }
try {
  $r.wlan = (& "$env:SystemRoot\System32\netsh.exe" wlan show interfaces | Out-String)
  if ($LASTEXITCODE -eq 0) { $r.sources.wlan = 'ok' } else { $r.sources.wlan = 'unavailable' }
} catch { $r.sources.wlan = 'unavailable' }
ConvertTo-Json -InputObject $r -Depth 5 -Compress
"""

GUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)


def guid(value):
    value = str(value or '').strip()
    if value.startswith('{') and value.endswith('}'):
        value = value[1:-1]
    return value.lower() if GUID.fullmatch(value) else None


def number(value):
    return value if type(value) is int else None


def text(value):
    return value[:2048] if isinstance(value, str) else ''


def rows(value):
    return [r for r in value if isinstance(r, dict)] if isinstance(value, list) else []


def parse_wlan(raw):
    """English netsh labels only; localised/denied/missing fields stay unknown.

    Bind each block by exact GUID, never by friendly name or output order.
    Channels 1–14 also exist in 6 GHz: never infer band from channel alone.
    """
    blocks, block = [], {}
    for line in raw.splitlines() if isinstance(raw, str) else []:
        m = re.match(r'^\s*(Name|GUID|State|Channel|Band)\s*:\s*(.*?)\s*$', line)
        if not m:
            continue
        key, value = m.groups()
        if key == 'Name':
            if block:
                blocks.append(block)
            block = {}
        block[key] = value
    if block:
        blocks.append(block)
    out = {}
    for b in blocks:
        identity = guid(b.get('GUID'))
        if not identity or identity in out:
            # Repeated identities cannot be joined reliably.
            if identity:
                out[identity] = {'channel': None, 'band': None}
            continue
        channel = b.get('Channel', '')
        channel = int(channel) if re.fullmatch(r'[0-9]{1,3}', channel) else None
        band = re.fullmatch(r'(2\.4|5|6)\s*GHz', b.get('Band', ''), re.I)
        connected = b.get('State') == 'connected'
        out[identity] = {'channel': channel if connected and channel and 1 <= channel <= 233 else None,
                         'band': band.group(1) if connected and band else None}
    return out


def analyse(data):
    if not isinstance(data, dict) or not isinstance(data.get('sources'), dict):
        raise ValueError('Invalid inventory')
    sources = {k: 'ok' if data['sources'].get(k) == 'ok' else 'unavailable'
               for k in ('pnp', 'present', 'adapters', 'routes', 'wlan')}
    present = {p.casefold() for p in (data.get('present') or []) if isinstance(p, str)}
    adapters = {}
    for a in rows(data.get('adapters')) if sources['adapters'] == 'ok' else []:
        key = text(a.get('PnPDeviceID')).casefold()
        if key:
            adapters.setdefault(key, []).append(a)
    routes = {r['InterfaceIndex'] for r in rows(data.get('routes'))
              if number(r.get('InterfaceIndex')) is not None} if sources['routes'] == 'ok' else set()
    wlan = parse_wlan(data.get('wlan', '')) if sources['wlan'] == 'ok' else {}
    devices, seen = [], set()
    inventory = rows(data.get('pnp')) if sources['pnp'] == 'ok' else []
    pnp_ids = {text(p.get('InstanceId')).casefold() for p in inventory}
    # Retain PC interfaces even when PnP inventory is incomplete/unavailable.
    inventory += [{'InstanceId': matches[0]['PnPDeviceID'],
                   'FriendlyName': matches[0].get('InterfaceDescription')}
                  for key, matches in adapters.items() if key not in pnp_ids]
    for p in inventory:
        identity = text(p.get('InstanceId'))
        if not identity or identity.casefold() in seen:
            continue
        seen.add(identity.casefold())
        matches = adapters.get(identity.casefold(), [])
        a = matches[0] if len(matches) == 1 else {}
        name = text(p.get('FriendlyName')) or text(a.get('InterfaceDescription')) or 'Unnamed network device'
        direct_id = identity.upper().startswith('SWD\\WIFIDIRECT\\')
        direct_name = re.sub(r'\s*#\d+$', '', name).casefold() == 'microsoft wi-fi direct virtual adapter'
        radio = wlan.get(guid(a.get('InterfaceGuid')), {})
        devices.append({
            'id': identity, 'name': name, 'interface': text(a.get('Name')),
            'wifiDirect': direct_id or direct_name,
            'identityEvidence': 'PnP enumerator' if direct_id else 'Name only' if direct_name else None,
            'wifi': number(a.get('NdisPhysicalMedium')) in (1, 9) if number(a.get('NdisPhysicalMedium')) is not None else None,
            'hardware': a.get('HardwareInterface') if type(a.get('HardwareInterface')) is bool else None,
            'present': identity.casefold() in present if sources['present'] == 'ok' else None,
            'pnpStatus': text(p.get('Status')) or None,
            'problemCode': number(p.get('Problem')),
            'operational': number(a.get('InterfaceOperationalStatus')),
            'media': number(a.get('MediaConnectState')),
            'defaultRoute': a['ifIndex'] in routes if number(a.get('ifIndex')) is not None and sources['routes'] == 'ok' else None,
            'channel': radio.get('channel'), 'band': radio.get('band'),
        })
    direct = [d['id'] for d in devices if d['wifiDirect']]
    return {'sources': sources, 'devices': devices, 'wifiDirectInstances': direct,
            'multipleWifiDirect': len(direct) > 1,
            'overlap': 'possible' if any(d['band'] == '2.4' for d in devices) else 'unknown',
            'state': 'ok' if all(s == 'ok' for s in sources.values()) else 'partial'}


def diagnose():
    """No cached inventory, automatic retries, UAC or SSH. One bounded probe."""
    if not frame_host.WINDOWS:
        return {'state': 'unsupported', 'message': 'Wireless Adapter doctor is available on a Windows PC.'}
    if not _lock.acquire(blocking=False):
        return {'state': 'busy', 'message': 'A PC wireless inventory is already running. Try again shortly.'}
    try:
        executable = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'),
                                  'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
        command = base64.b64encode(PROBE.encode('utf-16-le')).decode('ascii')
        result = subprocess.run([executable, '-NoProfile', '-NonInteractive', '-EncodedCommand', command],
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=TIMEOUT,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode or len(result.stdout) > 1_000_000:
            raise ValueError('Probe failed')
        report = analyse(json.loads(result.stdout.decode('utf-8-sig')))
        report['observedAt'] = datetime.now(timezone.utc).isoformat()
        return report
    except subprocess.TimeoutExpired:
        return {'state': 'unavailable', 'message': 'Windows wireless inventory timed out. No settings were changed.'}
    except (OSError, ValueError, TypeError):
        return {'state': 'unavailable', 'message': 'Windows wireless inventory could not be read. No settings were changed.'}
    finally:
        _lock.release()
