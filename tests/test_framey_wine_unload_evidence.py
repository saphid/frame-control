"""Replay real native Wine Cellar stop observations through the negative gate."""
import sandbox  # noqa: F401
import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location('wine_unload_evidence',
    ROOT/'decky-runtime/wine_cellar_private.py')
wine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wine)


class WineUnloadEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.observations = json.loads((ROOT/'fixtures/wine-unload-observations.json').read_text())

    def test_real_live_orphan_is_an_unclean_original_negative(self):
        self.assertEqual(wine.failed_unload_evidence(self.observations['liveOrphan']),
                         dict(zombieObserved=False, liveOrphanObserved=True))

    def test_real_zombie_is_an_unclean_original_negative(self):
        self.assertEqual(wine.failed_unload_evidence(self.observations['zombie']),
                         dict(zombieObserved=True, liveOrphanObserved=False))

    def test_real_clean_positive_cannot_qualify_as_an_original_failure(self):
        with self.assertRaises(AssertionError):
            wine.failed_unload_evidence(self.observations['cleanPositive'])

    def test_loader_failure_missing_shutdown_and_missing_forced_kill_are_rejected(self):
        for field, value in [('loaderReturncode', 1), ('console', ''),
                             ('forcedPluginKills', 0), ('forcedPluginKills', 2),
                             ('parentOnlySignal', False), ('cleanShutdownVerified', True)]:
            with self.subTest(field=field, value=value):
                observation = copy.deepcopy(self.observations['liveOrphan'])
                observation[field] = value
                with self.assertRaises(AssertionError):
                    wine.failed_unload_evidence(observation)

    def test_reused_process_identity_cannot_supply_either_failure_state(self):
        for name in ('liveOrphan', 'zombie'):
            with self.subTest(name=name):
                observation = copy.deepcopy(self.observations[name])
                observation['childBefore']['start'] = 'different-process-start'
                with self.assertRaises(AssertionError):
                    wine.failed_unload_evidence(observation)

    def test_live_orphan_requires_the_exact_helper_to_remain(self):
        observation = copy.deepcopy(self.observations['liveOrphan'])
        observation['exactChildRemaining'] = False
        with self.assertRaises(AssertionError):
            wine.failed_unload_evidence(observation)

    def test_live_helper_still_owned_by_its_parent_is_not_orphan_evidence(self):
        observation = copy.deepcopy(self.observations['liveOrphan'])
        for sample in observation['samples']:
            if sample['child']:
                sample['child']['parent'] = observation['childBefore']['parent']
        with self.assertRaises(AssertionError):
            wine.failed_unload_evidence(observation)
