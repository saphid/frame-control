"""Synthetic sysfs fixtures and loopback HTTP; never require an adapter or a Frame."""
import sandbox  # noqa: F401
import contextlib
import http.client
import io
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'ui'))
import frame_wireless_doctor as wd


class Parsers(unittest.TestCase):
    def test_channel_without_leaking_identifiers(self):
        for frequency, band, channel in [(2412, '2.4 GHz', 1), (5180, '5 GHz', 36), (5975, '6 GHz', 5)]:
            text = f'Interface wlan0\n addr aa:bb:cc:dd:ee:ff\n ssid private\n channel {channel} ({frequency} MHz), width: 80 MHz'
            self.assertEqual(wd.radio_info(text), dict(channel=channel, frequency_mhz=frequency, band=band))
        self.assertIsNone(wd.radio_info('Interface wlan0\n type managed\n'))
        self.assertEqual(wd.supported_frequencies('* 2412 MHz [1] (20.0 dBm)\n* 5975 MHz [5] (disabled)\n* 5180 MHz [36] (23.0 dBm)'), [2412, 5180])

    def test_non_linux_and_headset_mode_do_not_read_or_run(self):
        for kwargs in ({'system': 'darwin'}, {'system': 'win32'}, {'system': 'linux', 'local': True}):
            with patch.object(wd, 'Reader', side_effect=AssertionError('must not probe')):
                self.assertFalse(wd.diagnose(**kwargs)['supported'])
        with patch.dict(os.environ, {'FRAME_LOCAL': '1'}), patch.object(wd, 'Reader') as reader:
            self.assertFalse(wd.diagnose(system='linux')['supported'])
            reader.assert_not_called()

    def test_command_failure_is_not_empty_success(self):
        reader = wd.Reader()
        for error, status in [(FileNotFoundError(), 'missing'), (PermissionError(), 'unavailable'),
                              (subprocess.TimeoutExpired('iw', 3), 'timeout')]:
            with patch.object(wd.subprocess, 'run', side_effect=error):
                self.assertEqual(reader.command(['iw', 'dev', 'wlan0', 'info'])['status'], status)
        with patch.object(wd.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'Operation not permitted')) as run:
            result = reader.command(['iw', 'dev', 'wlan0', 'info'])
            self.assertEqual(result['status'], 'denied')
            self.assertEqual(result['text'], '')
            self.assertEqual(run.call_args.kwargs['stdin'], subprocess.DEVNULL)
            self.assertEqual(run.call_args.kwargs['timeout'], 3)
            self.assertNotIn('shell', run.call_args.kwargs)

    def test_read_failure_and_empty_inventory_remain_unknown(self):
        with tempfile.TemporaryDirectory() as root:
            reader = wd.Reader(root, root, root)
            report = wd.diagnose(reader=reader, system='linux', local=False)
        checks = {c['id']: c for c in report['checks']}
        self.assertEqual(checks['presence']['status'], 'unknown')
        self.assertIn('reads', checks)
        with patch.object(Path, 'open', side_effect=PermissionError()):
            self.assertIsNone(reader.read(Path('/synthetic/denied')))
        self.assertIn('PermissionError', reader.gaps[-1])


class Page(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is needed for real page script checks')
    def test_on_demand_selection_and_failure_recovery(self):
        result = subprocess.run(['node', str(Path(__file__).parent / 'page/wireless_doctor.mjs')],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class FixtureReader(wd.Reader):
    """Invented USB 1234:5678; it is deliberately not a claimed Valve ID."""
    def __init__(self, root):
        super().__init__(root / 'sys', root / 'dev', root / 'proc')
        self.commands = []
        self.responses = {}

    def command(self, argv):
        self.commands.append(argv)
        return self.responses.get(argv[0], {'status': 'missing', 'detail': argv[0] + ' is not installed', 'text': ''})


@unittest.skipUnless(sys.platform == 'linux', 'Linux sysfs symlink fixture')
class LinuxEvidence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.r = FixtureReader(self.root)
        self.usb = self.r.sysfs / 'devices/pci0000:00/usb1/1-2'
        for name, content in {'idVendor': '1234', 'idProduct': '5678', 'product': 'Synthetic adapter', 'busnum': '1', 'devnum': '2'}.items():
            self.write(self.usb / name, content)
        bus = self.r.sysfs / 'bus/usb/devices'
        bus.mkdir(parents=True)
        (bus / '1-2').symlink_to(self.usb, target_is_directory=True)
        (self.r.sysfs / 'class/net').mkdir(parents=True)
        (self.r.sysfs / 'class/rfkill').mkdir(parents=True)
        self.r.proc.mkdir(parents=True)
        self.write(self.r.dev / 'bus/usb/001/002', '')

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def nic(self, name='wlan0', index=0, driver=True):
        device = self.usb / f'1-2:1.{index}'
        device.mkdir(parents=True, exist_ok=True)
        net = self.r.sysfs / 'class/net' / name
        net.mkdir()
        (net / 'device').symlink_to(device, target_is_directory=True)
        (net / 'wireless').mkdir()
        self.write(net / 'operstate', 'down')
        phy = self.r.sysfs / f'devices/ieee80211/phy{index}'
        phy.mkdir(parents=True)
        (net / 'phy80211').symlink_to(phy, target_is_directory=True)
        if driver:
            binding = self.r.sysfs / 'bus/usb/drivers/synthetic_driver'
            binding.mkdir(parents=True, exist_ok=True)
            module = self.r.sysfs / 'module/synthetic_module'
            module.mkdir(parents=True, exist_ok=True)
            if not (binding / 'module').exists():
                (binding / 'module').symlink_to(module, target_is_directory=True)
            (device / 'driver').symlink_to(binding, target_is_directory=True)
        return net

    def report(self, device='usb:1-2'):
        return wd.diagnose(device, reader=self.r, system='linux', local=False)

    def checks(self, report):
        return {c['id']: c for c in report['checks']}

    def test_inventory_does_not_select_or_execute_commands(self):
        self.nic()
        report = self.report(None)
        self.assertIsNone(report['selected'])
        self.assertEqual(report['usb'][0]['interfaces'], ['net:wlan0'])
        self.assertEqual(report['interfaces'][0]['usb'], 'usb:1-2')
        self.assertIn('Unverified', report['identity'])
        self.assertEqual(self.r.commands, [])

    def test_nearest_usb_ancestor_wins_over_upstream_hub(self):
        hub = self.usb.parent / '1-1'
        hub.mkdir()
        old = self.usb
        self.usb = hub / old.name
        old.rename(self.usb)
        bus = self.r.sysfs / 'bus/usb/devices'
        (bus / '1-2').unlink()
        (bus / '1-2').symlink_to(self.usb, target_is_directory=True)
        for name, content in {'idVendor': '4321', 'idProduct': '8765', 'busnum': '1', 'devnum': '1'}.items():
            self.write(hub / name, content)
        (bus / '1-1').symlink_to(hub, target_is_directory=True)
        self.nic()
        report = self.report(None)
        self.assertEqual(report['interfaces'][0]['usb'], 'usb:1-2')
        upstream_hub = next(d for d in report['usb'] if d['port'] == '1-1')
        self.assertEqual(upstream_hub['interfaces'], [])

    def test_unbound_usb_is_selectable_without_guessing_driver(self):
        report = self.report()
        checks = self.checks(report)
        self.assertEqual(checks['binding']['status'], 'unknown')
        self.assertIn('No wireless interface', checks['binding']['evidence'][0])
        self.assertEqual(checks['channel']['status'], 'unknown')
        self.assertNotIn('iw', [a[0] for a in self.r.commands])
        self.assertIn('1234:5678', json.dumps(report))

    def test_selected_radio_and_all_commands_are_read_only(self):
        self.nic()
        for key, value in {'type': 'wlan', 'name': 'phy0', 'soft': '1', 'hard': '0'}.items():
            self.write(self.r.sysfs / 'class/rfkill/rfkill0' / key, value)
        for pid, name in enumerate(('NetworkManager', 'iwd', 'wpa_supplicant'), 1):
            self.write(self.r.proc / str(pid) / 'comm', name)
        self.r.responses = {
            'udevadm': dict(status='ok', detail='udevadm completed', text='ID_NET_DRIVER=synthetic_driver\nID_SERIAL=secret_serial\nTAGS=:uaccess:\n'),
            'iw': dict(status='ok', detail='iw completed', text='channel 5 (5975 MHz)\naddr aa:bb:cc:dd:ee:ff\nssid private\n* 5975 MHz [5] (23.0 dBm)'),
            'nmcli': dict(status='ok', detail='nmcli completed', text='30 (disconnected)\nyes\nsynthetic_driver\n')}
        report = self.report('net:wlan0')
        checks = self.checks(report)
        self.assertEqual(checks['binding']['status'], 'ok')
        self.assertIn('module=synthetic_module', checks['binding']['evidence'][0])
        self.assertEqual(checks['rfkill']['status'], 'warning')
        self.assertIn('6 GHz', json.dumps(checks['channel']))
        self.assertIn('coexistence alone is not a conflict', checks['managers']['suggestion'])
        self.assertIn('Both iwd and wpa_supplicant', checks['managers']['suggestion'])
        for secret in ('secret_serial', 'aa:bb:cc:dd:ee:ff', 'ssid private'):
            self.assertNotIn(secret, json.dumps(report))
        self.assertEqual(self.r.commands, [
            ['udevadm', 'info', '--query=property', '--path=' + str(self.r.sysfs / 'class/net/wlan0')],
            ['iw', 'dev', 'wlan0', 'info'], ['iw', 'phy', 'phy0', 'info'],
            ['nmcli', '-g', 'GENERAL.STATE,GENERAL.NM-MANAGED,GENERAL.DRIVER', 'device', 'show', 'wlan0']])

    def test_unrelated_rfkill_and_missing_tools_are_not_healthy(self):
        self.nic(driver=False)
        for key, value in {'type': 'wlan', 'name': 'phy7', 'soft': '1', 'hard': '1'}.items():
            self.write(self.r.sysfs / 'class/rfkill/rfkill7' / key, value)
        checks = self.checks(self.report())
        self.assertEqual(checks['binding']['status'], 'unknown')
        self.assertEqual(checks['rfkill']['status'], 'unknown')
        self.assertEqual(checks['permissions']['status'], 'unknown')
        self.assertEqual(checks['channel']['status'], 'unknown')
        self.r.responses['iw'] = dict(status='denied', detail='iw exited 1 (permission denied)', text='')
        self.assertIn('permission denied', json.dumps(self.checks(self.report())['channel']))

    def test_unmanaged_interface_does_not_trigger_a_network_repair(self):
        self.nic()
        self.r.responses['nmcli'] = dict(status='ok', detail='nmcli completed', text='10 (unmanaged)\nno\nsynthetic_driver\n')
        check = self.checks(self.report())['managers']
        self.assertIn('NetworkManager managed: no', check['evidence'])
        self.assertIn('unmanaged alone is not a fault', check['suggestion'])
        self.assertIn('Do not force management on', check['suggestion'])

    def test_multiple_interfaces_require_explicit_interface(self):
        self.nic()
        self.nic('wlan1', 1)
        checks = self.checks(self.report())
        self.assertIn('interface-selection', checks)
        self.assertEqual(checks['channel']['status'], 'unknown')
        self.assertNotIn('iw', [a[0] for a in self.r.commands])
        self.assertNotIn('interface-selection', self.checks(self.report('net:wlan1')))

    def test_disappeared_or_injected_selector_is_rejected_before_commands(self):
        for selector in ('net:missing', 'usb:../../etc', 'net:;sudo reboot', '', ['wlan0']):
            with self.assertRaises(ValueError):
                self.report(selector)
        self.assertEqual(self.r.commands, [])

    def test_cli_json_and_exit_contract(self):
        with patch.object(wd, 'diagnose', return_value=self.report(None)), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(wd.main(['--json']), 0)
        self.assertEqual(json.loads(out.getvalue())['schema'], 1)
        with patch.object(wd, 'diagnose', return_value={'supported': False}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(wd.main(['--json']), 2)


class HttpBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import server
        cls.server_module = server
        # Serve the real handler only: main() would start unrelated headset workers.
        cls.httpd = server.LoopbackServer(('127.0.0.1', 0), server.Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join()

    def request(self, path, key=True):
        conn = http.client.HTTPConnection('127.0.0.1', self.httpd.server_address[1], timeout=10)
        headers = {'X-Frame-UI': self.server_module.UI_KEY} if key else {}
        conn.request('GET', path, headers=headers)
        response = conn.getresponse()
        result = response.status, response.read()
        conn.close()
        return result

    def test_auth_and_headset_independence(self):
        with patch.object(self.server_module, 'ssh', side_effect=AssertionError('no SSH')), \
                patch.object(self.server_module, 'working', side_effect=AssertionError('no headset lock')), \
                patch.object(wd, 'diagnose', return_value={'supported': True, 'checks': []}) as probe:
            self.assertEqual(self.request('/api/wireless-doctor', key=False)[0], 403)
            probe.assert_not_called()
            code, data = self.request('/api/wireless-doctor?device=net%3Awlan0')
            self.assertEqual(code, 200)
            self.assertTrue(json.loads(data)['supported'])
            probe.assert_called_once_with('net:wlan0', local=self.server_module.LOCAL)

    def test_local_mode_refuses_before_collection(self):
        with patch.object(self.server_module, 'LOCAL', True), patch.object(wd, 'Reader', side_effect=AssertionError('no probes')):
            code, body = self.request('/api/wireless-doctor')
            self.assertEqual(code, 200)
            self.assertFalse(json.loads(body)['supported'])

    def test_stale_selection_is_bad_request_and_page_is_packaged(self):
        with patch.object(wd, 'diagnose', side_effect=ValueError('Device is no longer present')):
            self.assertEqual(self.request('/api/wireless-doctor?device=net:gone')[0], 400)
        code, page = self.request('/wireless-doctor')
        self.assertEqual(code, 200)
        self.assertIn(b'No checks have run', page)
        package = json.loads((Path(__file__).resolve().parent.parent / 'app/package.json').read_text())
        filters = next(r['filter'] for r in package['build']['extraResources'] if r['from'] == '../ui')
        self.assertIn('*.py', filters)
        self.assertIn('*.html', filters)
