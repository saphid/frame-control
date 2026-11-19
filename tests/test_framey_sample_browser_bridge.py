"""The native sample bridge preserves replies and rejects incomplete output."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sample_browser_replay', ROOT/'scripts/framey-test-sample-browser.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


@unittest.skipUnless(sys.platform.startswith('linux'), 'Native Linux pipe bridge')
class SampleBrowserBridge(unittest.TestCase):
    def run_bridge(self, code, exercise):
        process = subprocess.Popen([sys.executable, '-u', '-c', code], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        try:
            exercise(replay.Bridge(process))
        finally:
            process.kill()
            process.wait(timeout=3)
            process.stdin.close()
            process.stdout.close()

    def test_multiple_buffered_replies_are_consumed_separately(self):
        def exercise(bridge):
            self.assertEqual(bridge.read(), {'stage':'ready', 'cycle':0})
            self.assertEqual(bridge.read(), {'success':False, 'result':'saved bytes damaged'})
        self.run_bridge('print(\'{"stage":"ready","cycle":0}\\n{"success":false,"result":"saved bytes damaged"}\')', exercise)

    def test_request_and_reply_keep_false_values(self):
        def exercise(bridge):
            self.assertEqual(bridge.call({'op':'rpc','method':'get_setting','args':['enabled',True]}),
                             {'success':True,'result':False})
        self.run_bridge('import sys,json; request=json.loads(sys.stdin.readline()); assert request["args"]==["enabled",True]; print(json.dumps({"success":True,"result":False}))', exercise)

    def test_eof_does_not_accept_partial_json(self):
        self.run_bridge('import sys;sys.stdout.write(\'{"success":true}\')',
                        lambda bridge:self.assertRaisesRegex(RuntimeError,'before replying',bridge.read))

    def test_live_but_silent_bridge_has_a_bounded_failure(self):
        self.run_bridge('import time;time.sleep(5)',
                        lambda bridge:self.assertRaisesRegex(TimeoutError,'timed out',bridge.read,.05))

    def test_oversized_reply_is_refused(self):
        self.run_bridge('import sys;sys.stdout.write("x"*(2*1024**2+1));sys.stdout.flush()',
                        lambda bridge:self.assertRaisesRegex(ValueError,'exceeds bound',bridge.read))


if __name__=='__main__':unittest.main()
