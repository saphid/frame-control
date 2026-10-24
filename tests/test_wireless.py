"""PC-only wireless diagnosis: fixtures, HTTP boundaries and live Windows queries.

Never starts the app connector or contacts a headset, including on Windows CI.
"""
import sandbox  # noqa: F401
import base64
import copy
import http.client
import json
import shutil
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'ui'))
import frame_wireless as wireless
import server

G1 = '11111111-2222-3333-4444-555555555555'
G2 = '66666666-2222-3333-4444-555555555555'
DIRECT = 'SWD\\WIFIDIRECT\\one'
DIRECT2 = 'SWD\\WIFIDIRECT\\two'
PC = 'PCI\\radio'


def wlan(guid=G1, channel=1, band='2.4', state='connected'):
    return f'    Name : Wi-Fi\n    GUID : {{{guid}}}\n    State : {state}\n    Channel : {channel}\n    Band : {band} GHz\n'


def sample():
    return {'sources': dict.fromkeys(('pnp', 'present', 'adapters', 'routes', 'wlan'), 'ok'),
            'pnp': [{'InstanceId': DIRECT, 'FriendlyName': 'Microsoft Wi-Fi Direct Virtual Adapter', 'Status': 'OK', 'Problem': 0},
                    {'InstanceId': DIRECT2, 'FriendlyName': 'Microsoft Wi-Fi Direct Virtual Adapter #2', 'Status': 'Error', 'Problem': 22},
                    {'InstanceId': PC, 'FriendlyName': 'PC radio', 'Status': 'OK', 'Problem': 0}],
            'present': [DIRECT, PC],
            'adapters': [{'PnPDeviceID': DIRECT, 'InterfaceGuid': G2, 'ifIndex': 2, 'InterfaceOperationalStatus': 2, 'MediaConnectState': 2},
                         {'PnPDeviceID': PC, 'InterfaceGuid': '{' + G1.upper() + '}', 'ifIndex': 3,
                          'InterfaceOperationalStatus': 1, 'MediaConnectState': 1, 'NdisPhysicalMedium': 9, 'HardwareInterface': True}],
            'routes': [{'InterfaceIndex': 3}], 'wlan': wlan()}


class Inventory(unittest.TestCase):
    def test_distinct_instances_presence_disabled_and_activity_are_separate(self):
        r = wireless.analyse(sample())
        self.assertTrue(r['multipleWifiDirect'])
        self.assertEqual(r['wifiDirectInstances'], [DIRECT, DIRECT2])
        first, second, pc = r['devices']
        self.assertTrue(first['present'])
        self.assertEqual(first['operational'], 2)
        self.assertFalse(second['present'])
        self.assertEqual(second['problemCode'], 22)
        self.assertIsNone(second['operational'])
        self.assertTrue(pc['defaultRoute'])
        self.assertTrue(pc['wifi'])
        self.assertTrue(pc['hardware'])
        self.assertFalse(first['defaultRoute'])
        self.assertEqual(pc['channel'], 1)
        self.assertIsNone(first['channel'])
        self.assertEqual(r['overlap'], 'possible')

    def test_counts_unique_pnp_ids_not_rows_or_suffix_order(self):
        d = sample()
        d['pnp'].append(dict(d['pnp'][0], InstanceId=DIRECT.upper()))
        d['pnp'][1]['FriendlyName'] = 'Microsoft Wi-Fi Direct Virtual Adapter #57'
        r = wireless.analyse(d)
        self.assertEqual(len(r['wifiDirectInstances']), 2)
        self.assertEqual(len(r['devices']), 3)
        d['pnp'] = [dict(d['pnp'][0], FriendlyName='ローカライズされた名前')]
        d['adapters'] = []
        r = wireless.analyse(d)
        self.assertTrue(r['devices'][0]['wifiDirect'])
        self.assertEqual(r['devices'][0]['identityEvidence'], 'PnP enumerator')
        self.assertFalse(r['multipleWifiDirect'])

    def test_friendly_name_is_only_a_candidate_and_other_duplicate_names_are_not_direct(self):
        d = sample()
        d['pnp'] = [{'InstanceId': 'ROOT\\1', 'FriendlyName': 'Microsoft Wi-Fi Direct Virtual Adapter #4'},
                    {'InstanceId': 'ROOT\\2', 'FriendlyName': 'Ethernet'},
                    {'InstanceId': 'ROOT\\3', 'FriendlyName': 'Ethernet'}]
        d['adapters'] = []
        r = wireless.analyse(d)
        self.assertEqual(r['wifiDirectInstances'], ['ROOT\\1'])
        self.assertEqual(r['devices'][0]['identityEvidence'], 'Name only')

    def test_missing_sources_are_unknown_and_adapter_fallback_is_retained(self):
        for source in ('present', 'adapters', 'routes', 'wlan'):
            d = sample()
            d['sources'][source] = 'unavailable'
            r = wireless.analyse(d)
            pc = r['devices'][2]
            self.assertEqual(r['state'], 'partial')
            field = {'present': 'present', 'adapters': 'operational', 'routes': 'defaultRoute', 'wlan': 'channel'}[source]
            self.assertIsNone(pc[field])
        d = sample()
        d['sources']['pnp'] = 'unavailable'
        r = wireless.analyse(d)
        pc = next(x for x in r['devices'] if x['id'] == PC)
        self.assertTrue(pc['wifi'])
        self.assertIsNone(pc['pnpStatus'])

    def test_ambiguous_adapter_join_never_selects_the_first_match(self):
        d = sample()
        d['adapters'].append(copy.deepcopy(d['adapters'][1]))
        pc = wireless.analyse(d)['devices'][2]
        self.assertIsNone(pc['channel'])
        self.assertIsNone(pc['operational'])
        self.assertIsNone(pc['defaultRoute'])

    def test_missing_interface_metadata_and_invalid_guids_stay_unknown(self):
        d = sample()
        d['adapters'][1].pop('NdisPhysicalMedium')
        d['adapters'][1].pop('ifIndex')
        d['routes'].append({})
        pc = wireless.analyse(d)['devices'][2]
        self.assertIsNone(pc['wifi'])
        self.assertIsNone(pc['defaultRoute'])
        for invalid in ('{' + G1, G1 + '}', 'not-a-guid'):
            d['adapters'][1]['InterfaceGuid'] = invalid
            self.assertIsNone(wireless.analyse(d)['devices'][2]['channel'])

    def test_channels_require_exact_guid_and_band_is_never_guessed(self):
        d = sample()
        d['wlan'] = wlan(G2, 149, '5') + wlan(G1, 1, '6')
        r = wireless.analyse(d)
        self.assertEqual([(x['channel'], x['band']) for x in (r['devices'][0], r['devices'][2])], [(149, '5'), (1, '6')])
        self.assertEqual(r['overlap'], 'unknown')
        d['wlan'] = wlan().replace('    Band : 2.4 GHz\n', '')
        r = wireless.analyse(d)
        self.assertEqual(r['devices'][2]['channel'], 1)
        self.assertIsNone(r['devices'][2]['band'])
        self.assertEqual(r['overlap'], 'unknown')
        for raw in (wlan(G2), wlan(state='disconnected'), wlan(channel='oops'),
                    wlan().replace('Channel', 'チャネル'), 'Access denied. Location consent required.'):
            d['wlan'] = raw
            self.assertIsNone(wireless.analyse(d)['devices'][2]['channel'])
        d['wlan'] = wlan() + wlan()
        self.assertIsNone(wireless.analyse(d)['devices'][2]['channel'])

    def test_raw_ssid_mac_and_errors_are_not_returned(self):
        d = sample()
        d['wlan'] += '    SSID : private-network\n    BSSID : 11:22:33:44:55:66\nsecret error text\n'
        out = json.dumps(wireless.analyse(d))
        for value in ('private-network', '11:22:33:44:55:66', 'secret error text'):
            self.assertNotIn(value, out)


class Probe(unittest.TestCase):
    def test_non_windows_starts_nothing(self):
        with patch.object(wireless.frame_host, 'WINDOWS', False), patch.object(wireless.subprocess, 'run') as run:
            self.assertEqual(wireless.diagnose()['state'], 'unsupported')
            run.assert_not_called()

    def test_static_noninteractive_local_command_and_timeout(self):
        result = subprocess.CompletedProcess([], 0, json.dumps(sample()).encode(), b'')
        with patch.object(wireless.frame_host, 'WINDOWS', True), patch.object(wireless.subprocess, 'run', return_value=result) as run:
            r = wireless.diagnose()
            self.assertEqual(r['state'], 'ok')
            self.assertIn('observedAt', r)
            args, kwargs = run.call_args
            command = args[0]
            self.assertTrue(command[0].endswith('powershell.exe'))
            self.assertEqual(command[1:4], ['-NoProfile', '-NonInteractive', '-EncodedCommand'])
            self.assertEqual(base64.b64decode(command[4]).decode('utf-16-le'), wireless.PROBE)
            self.assertEqual(kwargs['stdin'], subprocess.DEVNULL)
            self.assertEqual(kwargs['timeout'], 20)
            self.assertNotIn('shell', kwargs)

    def test_failure_timeout_and_invalid_output_are_explicit_and_release_lock(self):
        for error in (OSError('private error'), subprocess.TimeoutExpired('powershell', 20)):
            with patch.object(wireless.frame_host, 'WINDOWS', True), patch.object(wireless.subprocess, 'run', side_effect=error):
                r = wireless.diagnose()
                self.assertEqual(r['state'], 'unavailable')
                self.assertNotIn('private error', json.dumps(r))
                self.assertFalse(wireless._lock.locked())
        for output in (b'not JSON', b'[]', b'{}', b'x' * 1_000_001):
            with patch.object(wireless.frame_host, 'WINDOWS', True), patch.object(wireless.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, output, b'')):
                self.assertEqual(wireless.diagnose()['state'], 'unavailable')

    def test_concurrent_requests_do_not_spawn_more_probes(self):
        wireless._lock.acquire()
        try:
            with patch.object(wireless.frame_host, 'WINDOWS', True), patch.object(wireless.subprocess, 'run') as run:
                self.assertEqual(wireless.diagnose()['state'], 'busy')
                run.assert_not_called()
        finally:
            wireless._lock.release()

    @unittest.skipUnless(wireless.frame_host.WINDOWS, 'Live read-only Windows inventory runs on Windows CI')
    def test_live_windows_inventory(self):
        r = wireless.diagnose()
        self.assertIn(r['state'], ('ok', 'partial'), r)
        self.assertEqual(r['sources']['adapters'], 'ok', r['sources'])
        self.assertTrue(r['devices'], 'Windows runner should expose at least its virtual network interface')
        print('Windows wireless smoke:', r['state'], r['sources'], 'devices=', len(r['devices']))

    def test_http_is_authenticated_pc_only_and_never_calls_ssh(self):
        httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(server, 'ssh', side_effect=AssertionError('No headset access')), patch.object(server.frame_wireless, 'diagnose', return_value={'state': 'partial'}) as diagnose:
                conn = http.client.HTTPConnection(*httpd.server_address)
                conn.request('GET', '/api/host/wireless')
                response = conn.getresponse()
                self.assertEqual(response.status, 403)
                response.read()
                diagnose.assert_not_called()
                with patch.object(server, 'LOCAL', True):
                    conn.request('GET', '/api/host/wireless', headers={'X-Frame-UI': server.UI_KEY})
                    response = conn.getresponse()
                    self.assertEqual(response.status, 400)
                    response.read()
                    diagnose.assert_not_called()
                with patch.object(server, 'LOCAL', False):
                    conn.request('GET', '/api/host/wireless', headers={'X-Frame-UI': server.UI_KEY})
                    response = conn.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read()), {'state': 'partial'})
                    diagnose.assert_called_once_with()
                conn.close()
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join()

    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_ui_behavior(self):
        r = subprocess.run(['node', '--test', str(ROOT / 'tests/wireless.cjs')], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
