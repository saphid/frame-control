"""Managed backend shims must stay covered by the actual-Decky CI gate."""
import sandbox  # noqa: F401
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('decky_runtime_gate', ROOT/'scripts/framey-test-decky-runtime.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class RuntimeCoverage(unittest.TestCase):
    def test_current_shims_have_unique_official_archive_probes(self):
        from framey_official import PLUGINS, PREFIX_MANAGER_102
        cases = gate.check_coverage()
        official = {record['id'] for record in PLUGINS}
        self.assertEqual(len(cases), len({(case['id'], case.get('version')) for case in cases}))
        for case in cases:
            self.assertIn(case['id'], official)
            if case.get('version'):
                self.assertEqual((case['id'], case['version']),
                                 (PREFIX_MANAGER_102['id'], PREFIX_MANAGER_102['version']))
            self.assertIn(case['probe'], ('bluetooth-private-bluez', 'deckyparty-private-files', 'mpris', 'screenshots', 'system-monitor', 'timer-lifecycle',
                                         'toggle-settings', 'fileserver', 'localsend', 'network-sentinel',
                                         'battery-tracker', 'free-loader', 'radio-local', 'game-sync-config',
                                         'shelves-settings', 'storage-cleaner', 'steamback-private-save',
                                         'suggestme-private', 'notifications-private',
                                         'emuchievements-private-hash', 'theme-music-settings',
                                         'deck-settings-readonly', 'steam-status-private-settings',
                                         'wine-cellar-private-state', 'prefix-manager', 'download-all-logging',
                                         'steamgriddb-private-artwork', 'protondb-private-settings',
                                         'desktop-apps-private-entries', 'tabmaster-private-settings', 'ludusavi-dependency-discovery',
                                         'deck-progress-private-tags', 'animation-private-overrides', 'nonsteam-private-shortcuts'))

    def test_new_shim_without_runtime_case_fails_coverage(self):
        import frame_decky_store
        with patch.object(frame_decky_store, 'APPLY', frame_decky_store.APPLY+
                          '\ncompat_shims.append("uncovered-new-shim")\n'):
            with self.assertRaisesRegex(ValueError, 'Every managed shim'):
                gate.check_coverage()

    def test_dynamic_shim_names_cannot_evade_inventory(self):
        import frame_decky_store
        with patch.object(frame_decky_store, 'APPLY', frame_decky_store.APPLY+
                          '\ncompat_shims.append(variable_name)\n'):
            with self.assertRaisesRegex(ValueError, 'literal name'):
                gate.check_coverage()
