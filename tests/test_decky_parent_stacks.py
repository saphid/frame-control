"""Verify stack attribution against the retained real published-loader capture."""
import sandbox  # noqa: F401
import copy
import gzip
import json
from pathlib import Path
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[1]
samples = runpy.run_path(str(ROOT/'tests/decky-runtime/parent_eof_stacks.py'))['listener_samples']


class ParentStackAttribution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder = ROOT/'docs/evidence/framey-parent-eof-stacks-2026-11-09'
        cls.stacks = gzip.decompress((folder/'stacks.raw.gz').read_bytes()).decode()
        trace = json.loads(gzip.decompress((folder/'successful-sampling-report.json.gz').read_bytes()))
        cls.native, = [json.loads(line.removeprefix('PROBE_REPORT '))
                       for line in trace['stdout'].splitlines() if line.startswith('PROBE_REPORT ')]

    def test_retained_capture_matches_independent_receipt(self):
        self.assertEqual(samples(self.stacks, self.native), dict(groups=65, samples=229, pids=[35]))

    def test_foreign_process_with_the_same_function_is_not_credited(self):
        native = copy.deepcopy(self.native)
        native['results'][1]['loaderPid'] = 999999
        self.assertEqual(samples(self.stacks, native), dict(groups=0, samples=0, pids=[]))

    def test_recorded_but_unrelated_descendant_is_not_credited(self):
        native = copy.deepcopy(self.native)
        native['results'][1]['descendantsBefore']['35']['parent'] = 999999
        self.assertEqual(samples(self.stacks, native), dict(groups=0, samples=0, pids=[]))

    def test_child_thread_cannot_be_attributed_to_its_parent(self):
        stacks = self.stacks.replace(';thread (35):', ';thread (48):')
        self.assertEqual(samples(stacks, self.native), dict(groups=0, samples=0, pids=[]))


if __name__ == '__main__':
    unittest.main()
