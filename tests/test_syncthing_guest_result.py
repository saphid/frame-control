"""Screenshot evidence must survive short writes and reject any lost bytes."""
import importlib.util
import io
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('guest_result', ROOT/'tests/decky-runtime/guest_result.py')
packet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packet)


class GuestEvidence(unittest.TestCase):
    def test_large_eight_capture_report_survives_short_serial_writes(self):
        report = dict(success=True, screenshots={str(i): 'private-capture-'*20000 for i in range(8)},
                      diagnostic='quoted " unicode \u2603 and newline\n', realFrameContacted=False)
        class ShortSerial(io.BytesIO):
            def write(self, data):
                return super().write(data[:317])
        stream = ShortSerial()
        packet.write_result(stream, report)
        self.assertEqual(packet.decode(stream.getvalue()), report)

    def test_missing_duplicate_reordered_corrupted_or_trailing_bytes_are_refused(self):
        original = packet.encode(dict(success=True, marker='abc'))
        header, _, body = original.partition(b'\n')
        for changed in (b'', original[:-1], original[1:], original+original,
                        original+b'log', body+header, original.replace(b'abc', b'xyz'),
                        original.replace(b'FRAMEY_GUEST_RESULT_END', b'FRAMEY_GUEST_RESULT_BAD')):
            with self.subTest(size=len(changed)), self.assertRaises(ValueError):
                packet.decode(changed)

    def test_complete_failure_report_is_preserved_as_failure(self):
        report = dict(success=False, partial=dict(ownedProcessesReaped=True), error='owned peer not ready')
        self.assertEqual(packet.decode(packet.encode(report)), report)

    def test_bound_and_object_requirement_cannot_be_bypassed(self):
        for value in ([], dict(value='x'*packet.MAX_PAYLOAD), dict(value=float('nan'))):
            with self.subTest(kind=type(value).__name__), self.assertRaises(ValueError):
                packet.encode(value)
        for size in (b'0', b'-1', str(packet.MAX_PAYLOAD+1).encode(), b'garbage'):
            with self.assertRaises(ValueError):
                packet.decode(packet.MAGIC+b' '+size+b' checksum\n{}'+packet.END)

    def test_stalled_or_invalid_writer_never_reports_completion(self):
        class BrokenSerial:
            def write(self, _data): return 0
        with self.assertRaises(OSError):
            packet.write_result(BrokenSerial(), dict(success=True))
