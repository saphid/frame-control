"""Pure synthetic sidecar/runner controls: no procfs, network, child or VM."""
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
import sidecar_transport as transport
import live_boundary
import observe_fixture as driver
import retain_report


class Transport(unittest.TestCase):
    def fixture(self, home):
        report = dict(id=65, runtimeConsole=dict(probeCompleted=False, cleanupCompleted=True))
        native = retain_report.retain(home / transport.FILES['nativeReport'], report)
        observation = live_boundary.Observation(enabled=True, reader=lambda _: b'', clock=lambda: 1)
        observation.phase('discovery-entered')
        with patch.object(driver, 'OBSERVATION', home / transport.FILES['observation']), \
             patch.object(driver, 'RECEIPT', home / transport.FILES['receipt']):
            driver.finish_sidecars(observation, native)
        return report

    def test_actual_producers_retain_failed_native_report_without_success_inference(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder); original = self.fixture(home)
            result = transport.collect(home=home, uid=os.getuid())
            self.assertTrue(result['receiptValid'])
            self.assertEqual(result['nativeReport'], original)
            self.assertFalse(result['nativeReport']['runtimeConsole']['probeCompleted'])
            self.assertTrue(result['observation']['complete'])
            self.assertFalse(result['nativePassInferred'])
            self.assertFalse(result['qualificationPassed'])
            self.assertFalse(result['observation']['tokenResponseBodyCompletionObserved'])

    def test_missing_truncated_digest_mismatch_do_not_become_available(self):
        for mode in ['missing', 'partial', 'different-valid-json']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                home = Path(folder); self.fixture(home)
                path = home / transport.FILES['observation']
                if mode == 'missing': path.unlink()
                elif mode == 'partial': path.write_bytes(b'{')
                else: path.write_bytes(b'{"syntheticDifferent":true}')
                result = transport.collect(home=home, uid=os.getuid())
                self.assertNotIn('observation', result)
                self.assertFalse(result['sidecars']['observation']['matchesDriverReceipt'])
                self.assertIn('nativeReport', result)

    def test_symlink_hardlink_fifo_owner_mode_and_cap_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder); file = home / 'file'; file.write_bytes(b'{}'); file.chmod(0o600)
            link = home / 'symlink'; link.symlink_to(file)
            fifo = home / 'fifo'; os.mkfifo(fifo, 0o600)
            for path in [link, fifo]:
                self.assertIsNone(transport.read_json(path, uid=os.getuid())[0])
            self.assertIsNone(transport.read_json(file, uid=os.getuid()+1)[0])
            hard = home / 'hard'; os.link(file, hard)
            self.assertIsNone(transport.read_json(file, uid=os.getuid())[0]); hard.unlink()
            file.chmod(0o644)
            self.assertIsNone(transport.read_json(file, uid=os.getuid())[0]); file.chmod(0o600)
            file.write_bytes(b' ' * 32769)
            self.assertIsNone(transport.read_json(file, uid=os.getuid())[0])

    def test_changed_file_and_failed_close_remain_unavailable(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'file'; path.write_bytes(b'{}'); path.chmod(0o600)
            real = path.stat()
            class Changed:
                def __getattr__(self, name): return getattr(real, name) + (1 if name == 'st_size' else 0)
            with patch.object(transport.os, 'fstat', side_effect=[real, Changed()]):
                self.assertIsNone(transport.read_json(path, uid=os.getuid())[0])
            close = os.close
            def close_then_raise(fd): close(fd); raise OSError('PRIVATE_ERROR')
            with patch.object(transport.os, 'close', side_effect=close_then_raise):
                value, status = transport.read_json(path, uid=os.getuid())
            self.assertIsNone(value); self.assertNotIn('PRIVATE_ERROR', json.dumps(status))

    def test_duplicate_nonfinite_nonobject_and_invalid_receipt_refused(self):
        for raw in [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b'{"a":-1e999}', b'[]']:
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder)/'file'; path.write_bytes(raw); path.chmod(0o600)
                self.assertIsNone(transport.read_json(path, uid=os.getuid())[0])
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder); self.fixture(home)
            path=home/transport.FILES['receipt']; receipt=json.loads(path.read_bytes())
            receipt['fixtureSourceSha256']='0'*64; path.write_text(json.dumps(receipt))
            result=transport.collect(home=home,uid=os.getuid())
            self.assertFalse(result['receiptValid']); self.assertNotIn('observation',result)
            self.assertNotIn('nativeReport',result)

    def test_matching_receipt_with_overflow_cannot_break_exact_failed_result_packet(self):
        codec = {'__name__': 'private_exact_main_codec'}
        source = Path.cwd() / 'tests/decky-runtime/guest_result.py'
        exec(compile(source.read_bytes(), str(source), 'exec'), codec)
        for raw in [b'{"value":1e999}', b'{"nested":[-1e999]}']:
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as folder:
                home=Path(folder); self.fixture(home)
                path=home/transport.FILES['observation']; path.write_bytes(raw)
                receipt_path=home/transport.FILES['receipt']; receipt=json.loads(receipt_path.read_bytes())
                receipt['loopbackObservation'].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
                receipt_path.write_text(json.dumps(receipt))
                collected=transport.collect(home=home,uid=os.getuid())
                self.assertNotIn('observation',collected)
                report={'success':False,'loopbackDiagnostic':collected}
                self.assertEqual(codec['decode'](codec['encode'](report)),report)


if __name__ == '__main__': unittest.main(verbosity=2)
