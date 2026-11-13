"""Read-only Linux PC Wireless Adapter doctor. No SSH, scans or repairs.

Run on the PC: python3 ui/frame_wireless_doctor.py [--device net:wlan0] [--json]
USB IDs are observations, never a claim that a device is Valve's adapter.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys


class Reader:
    """Bounded local reads; failures remain evidence rather than healthy defaults."""
    def __init__(self, sysfs=Path('/sys'), dev=Path('/dev'), proc=Path('/proc')):
        self.sysfs, self.dev, self.proc = Path(sysfs), Path(dev), Path(proc)
        self.gaps = []

    def read(self, path):
        try:
            with path.open(errors='replace') as source:
                return source.read(4096).strip()
        except OSError as exc:
            self.gaps.append(f'{path}: {type(exc).__name__}')
            return None

    def entries(self, path):
        try:
            return sorted(path.iterdir())
        except OSError as exc:
            self.gaps.append(f'{path}: {type(exc).__name__}')
            return []

    def link(self, path):
        try:
            return path.resolve(strict=True).name
        except OSError as exc:
            if not isinstance(exc, FileNotFoundError):
                self.gaps.append(f'{path}: {type(exc).__name__}')
            return None

    def command(self, argv):
        try:
            result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                                    text=True, errors='replace', timeout=3,
                                    env={**os.environ, 'LC_ALL': 'C'})
        except FileNotFoundError:
            return {'status': 'missing', 'detail': f'{argv[0]} is not installed', 'text': ''}
        except subprocess.TimeoutExpired:
            return {'status': 'timeout', 'detail': f'{argv[0]} timed out', 'text': ''}
        except OSError as exc:
            return {'status': 'unavailable', 'detail': f'{argv[0]}: {type(exc).__name__}', 'text': ''}
        if result.returncode:
            # Do not export command output that may contain SSIDs, MACs or other identifiers.
            denied = bool(re.search(r'permission|not permitted|access denied', result.stderr, re.I))
            return {'status': 'denied' if denied else 'unavailable',
                    'detail': f'{argv[0]} exited {result.returncode}' + (' (permission denied)' if denied else ''),
                    'text': ''}
        return {'status': 'ok', 'detail': f'{argv[0]} completed', 'text': result.stdout[:131072]}


def inventory(reader):
    usb = []
    for path in reader.entries(reader.sysfs / 'bus/usb/devices'):
        # USB interface entries have no idVendor; inspect them under their parent below.
        if ':' in path.name or not (path / 'idVendor').exists():
            continue
        vid, pid = reader.read(path / 'idVendor'), reader.read(path / 'idProduct')
        bindings = []
        for child in reader.entries(path):
            if ':' in child.name:
                bindings.append({'interface': child.name, 'driver': reader.link(child / 'driver'),
                                 'module': reader.link(child / 'driver/module')})
        usb.append({'id': 'usb:' + path.name, 'port': path.name, 'vid': vid, 'pid': pid,
                    'product': reader.read(path / 'product') if (path / 'product').exists() else None,
                    'bus': reader.read(path / 'busnum'), 'number': reader.read(path / 'devnum'),
                    'bindings': bindings, 'interfaces': []})
    interfaces = []
    for path in reader.entries(reader.sysfs / 'class/net'):
        if not ((path / 'wireless').exists() or (path / 'phy80211').exists()):
            continue
        try:
            device_path = (path / 'device').resolve(strict=True)
            ancestors = [device_path, *device_path.parents]
        except OSError:
            ancestors = []
        # Nearest USB ancestor: a downstream adapter must not be attributed to its hub.
        by_port = {d['port']: d for d in usb}
        parent = next((by_port[p.name] for p in ancestors if p.name in by_port), None)
        item = {'id': 'net:' + path.name, 'name': path.name,
                'usb': parent['id'] if parent else None, 'phy': reader.link(path / 'phy80211'),
                'driver': reader.link(path / 'device/driver'),
                'module': reader.link(path / 'device/driver/module'),
                'state': reader.read(path / 'operstate')}
        interfaces.append(item)
        if parent:
            parent['interfaces'].append(item['id'])
    return usb, interfaces


def radio_info(text):
    """Parse only channel facts; omit interface MAC, SSID and link identifiers."""
    match = re.search(r'channel (\d+) \((\d+) MHz\)', text)
    if not match:
        return None
    frequency = int(match[2])
    band = '2.4 GHz' if 2400 <= frequency < 2500 else '5 GHz' if 4900 <= frequency < 5925 else '6 GHz' if 5925 <= frequency <= 7125 else 'other'
    return {'channel': int(match[1]), 'frequency_mhz': frequency, 'band': band}


def supported_frequencies(text):
    return sorted(set(int(n) for n in re.findall(r'\* (\d+) MHz \[\d+\](?![^\n]*disabled)', text)))


def diagnose(device=None, *, reader=None, system=None, local=None):
    """Collect only on explicit request. The server calls this outside headset work."""
    report = {'schema': 1, 'captured_at': datetime.now(timezone.utc).isoformat(), 'scope': 'Linux PC only; read-only', 'supported': False,
              'identity': 'Unverified: select hardware by its observed USB port or network interface. '
                          'No trusted Steam Frame Wireless Adapter VID/PID is assumed.',
              'selected': device, 'usb': [], 'interfaces': [], 'checks': []}
    def check(key, status, title, evidence, suggestion):
        report['checks'].append(dict(id=key, status=status, title=title,
                                     evidence=evidence, suggestion=suggestion))
    if (system or sys.platform) != 'linux' or (os.environ.get('FRAME_LOCAL') == '1' if local is None else local):
        check('platform', 'unknown', 'Linux PC required', [],
              'Run this doctor on the Linux PC, not on the Frame or the phone server.')
        return report
    report.update(supported=True, kernel=platform.release())
    r = reader or Reader()
    usb, interfaces = inventory(r)
    report.update(usb=usb, interfaces=interfaces)
    items = usb + interfaces
    selected = next((d for d in items if d['id'] == device), None)
    if device is not None and selected is None:
        raise ValueError('Device is no longer present. Refresh and select an observed device.')
    check('presence', 'ok' if items else 'unknown', 'USB and wireless interface presence',
          [f'{len(usb)} USB devices; {len(interfaces)} wireless interfaces visible in sysfs'],
          'Select the intended adapter. USB presence alone does not establish wireless support.' if items else
          'No candidates are visible. Check the PC USB connection and whether a VM/container hides hardware; this does not prove the adapter is absent.')
    if selected is None:
        check('selection', 'unknown', 'Hardware identity needs selection', [],
              'Compare the inventory before and after reconnecting the adapter when safe. Select its USB port even if no network interface exists.')
        if r.gaps:
            check('reads', 'unknown', 'Some local evidence is unavailable', r.gaps,
                  'Review unavailable paths locally; do not infer healthy hardware from missing evidence.')
        return report
    correlated = [d for d in interfaces if d['usb'] == device]
    nic = selected if device.startswith('net:') else correlated[0] if len(correlated) == 1 else None
    if len(correlated) > 1:
        check('interface-selection', 'unknown', 'More than one wireless interface',
              [d['id'] for d in correlated], 'Select a network interface for per-interface radio and ownership checks.')
    parent = selected if device.startswith('usb:') else next((d for d in usb if d['id'] == selected['usb']), None)
    names = [d['name'] for d in interfaces if parent and d['usb'] == parent['id']]
    check('binding', 'ok' if nic and nic['driver'] else 'unknown', 'Driver and module binding',
          ([f"{nic['name']}: driver={nic['driver'] or 'unavailable'}, module={nic['module'] or 'unavailable (possibly built in)'}, state={nic['state'] or 'unknown'}"] if nic else ['Multiple wireless interfaces are correlated; select one explicitly.' if len(correlated) > 1 else 'No wireless interface is correlated with this USB device.']) +
          ([f"USB {parent['port']} observed ID {parent['vid']}:{parent['pid']}; wireless interfaces: {', '.join(names) or 'none'}"] +
           [f"{b['interface']}: driver={b['driver'] or 'unbound'}, module={b['module'] or 'unavailable'}" for b in parent['bindings']] if parent else []),
          'A bound driver does not prove streaming support. A missing module link can mean a built-in driver.' if nic and nic['driver'] else
          'Check this observed device ID against your distribution/kernel and vendor documentation. No driver package or cause can be inferred; do not install a guessed driver or disable Secure Boot.')
    path = r.sysfs / ('class/net/' + nic['name'] if nic else 'bus/usb/devices/' + parent['port'])
    udev = r.command(['udevadm', 'info', '--query=property', '--path=' + str(path)])
    properties = [line for line in udev['text'].splitlines() if line.split('=', 1)[0] in
                  ('ID_NET_DRIVER', 'ID_USB_DRIVER', 'ID_VENDOR_ID', 'ID_MODEL_ID', 'TAGS', 'CURRENT_TAGS')]
    access = []
    if parent and (parent['bus'] or '').isdigit() and (parent['number'] or '').isdigit():
        node = r.dev / f"bus/usb/{int(parent['bus']):03d}/{int(parent['number']):03d}"
        try:
            st = node.stat()
            access.append(f'{node}: mode={stat.S_IMODE(st.st_mode):04o}, uid={st.st_uid}, gid={st.st_gid}, '
                          f'user read={os.access(node, os.R_OK)}, write={os.access(node, os.W_OK)}')
        except OSError as exc:
            access.append(f'{node}: {type(exc).__name__}')
    check('permissions', 'info' if udev['status'] == 'ok' else 'unknown', 'Permissions and udev evidence',
          [udev['detail'], *properties, *access],
          'USB node access is only an observation; kernel networking may not require direct USB access. '
          'If Steam reports access denied for this exact device, compare the vendor/distribution udev guidance. Do not use broad chmod rules or run Steam as root.')
    blocks = []
    for entry in r.entries(r.sysfs / 'class/rfkill'):
        if r.read(entry / 'type') != 'wlan':
            continue
        phy = r.read(entry / 'name')
        blocks.append({'name': phy, 'soft': r.read(entry / 'soft'), 'hard': r.read(entry / 'hard'),
                       'selected_phy': bool(nic and nic['phy'] and phy == nic['phy'])})
    relevant = [b for b in blocks if b['selected_phy']]
    blocked = any(b[k] == '1' for b in relevant for k in ('soft', 'hard'))
    complete = relevant and all(b[k] in ('0', '1') for b in relevant for k in ('soft', 'hard'))
    check('rfkill', 'warning' if blocked else 'ok' if complete else 'unknown', 'Radio blocks',
          [f"{b['name']}: soft={b['soft']}, hard={b['hard']}, selected PHY={b['selected_phy']}" for b in blocks] or ['No readable WLAN rfkill entries.'],
          'The selected PHY is blocked. Review the PC radio switch/airplane mode; a hard block may need a hardware switch.' if blocked else
          'Only a matching PHY establishes this adapter’s rfkill state. Unrelated or unavailable entries do not rule out a radio block.')
    if nic:
        iw = r.command(['iw', 'dev', nic['name'], 'info'])
        radio = radio_info(iw['text'])
        frequencies = []
        phy = nic['phy']
        if phy and re.fullmatch(r'phy\d+', phy):
            capabilities = r.command(['iw', 'phy', phy, 'info'])
            frequencies = supported_frequencies(capabilities['text'])
        else:
            capabilities = {'detail': 'No PHY identifier available'}
        check('channel', 'info' if radio else 'unknown', 'Current channel and band',
              [iw['detail'], json.dumps(radio) if radio else 'No current channel reported.',
               capabilities['detail'], f'Enabled frequencies reported by iw (MHz): {frequencies or "unavailable"}'],
              'This is local radio evidence, not proof of the Steam streaming link or supported regions. '
              'If no channel is reported the radio may be idle. Do not force a band, channel or regulatory country.')
        nm = r.command(['nmcli', '-g', 'GENERAL.STATE,GENERAL.NM-MANAGED,GENERAL.DRIVER', 'device', 'show', nic['name']])
        # These fields contain no SSIDs, addresses or credentials.
        fields = nm['text'].strip().splitlines()[:3] if nm['status'] == 'ok' else []
        nm_evidence = [f'{label}: {value}' for label, value in zip(
            ('NetworkManager state', 'NetworkManager managed', 'NetworkManager driver'), fields)]
        unmanaged = len(fields) > 1 and fields[1].lower() == 'no'
    else:
        nm = {'detail': 'No correlated wireless interface; per-interface ownership unavailable'}
        nm_evidence = []
        unmanaged = False
        check('channel', 'unknown', 'Current channel and band', [], 'Select one correlated network interface to check channel/band.' if len(correlated) > 1 else 'No correlated wireless interface exists; channel/band cannot be determined.')
    processes = set()
    proc_entries = r.entries(r.proc)
    for entry in proc_entries:
        if entry.name.isdigit():
            comm = r.read(entry / 'comm')
            if comm in ('NetworkManager', 'iwd', 'wpa_supplicant'):
                processes.add(comm)
    check('managers', 'info' if proc_entries else 'unknown', 'Network manager coexistence',
          [f'Visible processes: {", ".join(sorted(processes)) or "none"}', nm['detail'], *nm_evidence],
          'NetworkManager commonly uses iwd or wpa_supplicant as its Wi-Fi backend; coexistence alone is not a conflict. '
          + ('Both iwd and wpa_supplicant are visible. Check locally which service owns the selected interface before attributing a conflict; do not stop either automatically.' if {'iwd', 'wpa_supplicant'} <= processes else
             'Per-interface ownership by iwd/wpa_supplicant is unverified. Process absence in a restricted /proc view is inconclusive.')
          + (' NetworkManager reports this interface unmanaged. Steam or another service may own it; unmanaged alone is not a fault. Do not force management on.' if unmanaged else ''))
    if r.gaps:
        check('reads', 'unknown', 'Some local evidence is unavailable', r.gaps[:40],
              'Review unavailable paths locally. Permission failures or disappearing devices are not evidence of an adapter fault; do not elevate this doctor.')
    check('limits', 'info', 'What this report cannot establish', [],
          'No physical adapter or Frame link test runs here. Firmware, USB stability under load, Steam support and the reported Ubuntu/Kubuntu 26.04 cause remain unverified. Review the report before sharing it.')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--device', help='observed selector, e.g. net:wlan0 or usb:1-2; omitted lists candidates')
    parser.add_argument('--json', action='store_true', help='print structured local evidence; review before sharing')
    args = parser.parse_args(argv)
    try:
        data = diagnose(args.device)
    except ValueError as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(data['scope'] + '\n' + data['identity'])
        for d in data['usb']:
            print(f"  {d['id']}  {d['vid']}:{d['pid']}  {d['product'] or 'unnamed USB device'}")
        for d in data['interfaces']:
            print(f"  {d['id']}  USB={d['usb'] or 'not correlated'}  driver={d['driver'] or 'unknown'}")
        for c in data['checks']:
            print(f"\n[{c['status'].upper()}] {c['title']}")
            for line in c['evidence']:
                print('  ' + line)
            print('  ' + c['suggestion'])
    return 0 if data['supported'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
