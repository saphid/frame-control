"""The release smoke gate requires a complete result from its exact checkout."""

import importlib.util
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    'verify_frame_smoke_result', ROOT / 'scripts' / 'verify-frame-smoke-result.py')
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)
SHA = 'a' * 40


def result():
    steps = [{'step': name, 'ok': True} for name in sorted(gate.REQUIRED_STEPS)]
    return {'source': {'commit': SHA, 'clean': True}, 'lock_released': True, 'steps': steps,
            'passed': len(steps), 'skipped': 0, 'failed': 0,
            'preflight': {'activity': 3, 'proximity': [2.3125], 'battery': [100]}}


class VerifyFrameSmokeResult(unittest.TestCase):
    def test_accepts_complete_clean_result_from_exact_commit(self):
        gate.verify(result(), SHA)

    def test_rejects_wrong_commit_dirty_checkout_or_missing_step(self):
        for changed in ('commit', 'clean', 'step'):
            with self.subTest(changed=changed):
                data = result()
                if changed == 'commit':
                    data['source']['commit'] = 'b' * 40
                elif changed == 'clean':
                    data['source']['clean'] = False
                else:
                    data['steps'].pop()
                    data['passed'] -= 1
                with self.assertRaises(ValueError):
                    gate.verify(data, SHA)

    def test_rejects_skipped_launch_even_when_counts_claim_success(self):
        data = result()
        launch = next(step for step in data['steps'] if step['step'] == 'x86_64: launch')
        launch.update(ok=False, skipped=True)
        data.update(passed=len(data['steps']) - 1, skipped=1)
        with self.assertRaisesRegex(ValueError, 'failed, skipped'):
            gate.verify(data, SHA)

    def test_rejects_missing_locked_preflight(self):
        data = result()
        data['preflight']['activity'] = 1
        with self.assertRaisesRegex(ValueError, 'preflight'):
            gate.verify(data, SHA)

    def test_rejects_nonfinite_proximity_and_invalid_battery(self):
        for proximity in (math.nan, math.inf, -math.inf):
            with self.subTest(proximity=proximity):
                data = result()
                data['preflight']['proximity'] = [proximity]
                with self.assertRaisesRegex(ValueError, 'preflight'):
                    gate.verify(data, SHA)
        for battery in ([True], [math.nan], [101], [19], ['99']):
            with self.subTest(battery=battery):
                data = result()
                data['preflight']['battery'] = battery
                with self.assertRaisesRegex(ValueError, 'preflight'):
                    gate.verify(data, SHA)

    def test_rejects_missing_lock_release_record(self):
        data = result()
        data['lock_released'] = False
        with self.assertRaisesRegex(ValueError, 'lock release'):
            gate.verify(data, SHA)


if __name__ == '__main__':
    unittest.main()
