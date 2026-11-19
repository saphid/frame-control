"""Bounded package preparation refuses incorrect metadata and unsafe cache inputs."""

import hashlib
import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

try:
    from gi.repository import GLib
except ImportError:
    GLib = None


@unittest.skipIf(GLib is None, "The offline preparation environment requires GI")
class PreparationInput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = (
            Path(__file__).resolve().parents[1]
            / "scripts/framey-prepare-syncthing-flatpak.py"
        )
        spec = importlib.util.spec_from_file_location("flatpak_prepare", path)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_changed_descriptor_is_refused_before_key_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            descriptor = Path(temporary) / "flathub.flatpakrepo"
            descriptor.write_bytes(b"[Flatpak Repo]\nGPGKey=ZGF0YQ==\n")
            with self.assertRaisesRegex(ValueError, "descriptor"):
                self.module.public_key(descriptor)

    def test_unexpected_commit_ref_stops_before_fetching_child_content(self):
        metadata = {
            "ostree.ref-binding": GLib.Variant("as", ["app/wrong.name/x86_64/stable"]),
            "ostree.collection-binding": GLib.Variant("s", "org.flathub.Stable"),
        }
        commit = GLib.Variant(
            "(a{sv}aya(say)sstayay)",
            (metadata, b"", [], "subject", "body", 0, bytes(32), bytes(32)),
        )
        data = commit.get_data_as_bytes().get_data()
        checksum = hashlib.sha256(data).hexdigest()
        visited = []

        def download(url, _limit):
            visited.append(url)
            return data if url.endswith(".commit") else b"detached signature"

        with tempfile.TemporaryDirectory() as temporary, patch.object(
            self.module, "pins", return_value={"app": checksum}
        ), patch.object(
            self.module, "public_key", return_value=b"pinned key"
        ), patch.object(
            self.module.fetcher, "download", side_effect=download
        ):
            directory = Path(temporary) / "new-closure"
            with self.assertRaisesRegex(ValueError, "binding"):
                self.module.fetch(directory, "x86_64", [])
            self.assertEqual(
                len(visited), 3
            )  # Descriptor, commit and detached signature only.
            self.assertIn(
                '"payloadIntegrityVerified": false',
                (directory / "fetch-report.json").read_text(),
            )

    def test_seed_symlink_cannot_be_used_as_a_payload_object(self):
        checksum = "a" * 64
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seed = root / "seed"
            (seed / "aa").mkdir(parents=True)
            foreign = root / "foreign"
            foreign.write_bytes(b"preserve me")
            (seed / "aa" / (checksum[2:] + ".commit")).symlink_to(foreign)
            with patch.object(
                self.module, "pins", return_value={"app": checksum}
            ), patch.object(
                self.module, "public_key", return_value=b"pinned key"
            ), patch.object(
                self.module.fetcher, "download", return_value=b"descriptor"
            ):
                with self.assertRaisesRegex(ValueError, "Unsafe"):
                    self.module.fetch(root / "closure", "x86_64", [seed])
            self.assertEqual(foreign.read_bytes(), b"preserve me")

    def test_real_timeout_retains_diagnostics_and_reaps_without_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / 'started'
            records = []
            code = (
                'import os,time; from pathlib import Path; '
                'p=Path(__import__("sys").argv[1]); '
                'p.open("a").write(str(os.getpid())+"\\n"); '
                'print("partial-output",flush=True); '
                'time.sleep(30)'
            )
            with contextlib.redirect_stdout(io.StringIO()) as captured:
                with self.assertRaises(subprocess.TimeoutExpired):
                    self.module.run([sys.executable, '-c', code, str(marker)],
                                    timeout=0.5, observations=records)
            pids = marker.read_text().splitlines()
            self.assertEqual(len(pids), 1)
            with self.assertRaises(ProcessLookupError):
                os.kill(int(pids[0]), 0)
            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertFalse(record['success'])
            self.assertTrue(record['timedOut'])
            self.assertEqual(record['timeoutSeconds'], 0.5)
            self.assertIn('partial-output', record['stdoutTail'])
            self.assertGreaterEqual(record['elapsedSeconds'], 0.5)
            self.assertGreaterEqual(record['waitedChildUserCpuSeconds'], 0)
            emitted = captured.getvalue().split('FRAMEY_PREPARATION_COMMAND_JSON=')[1]
            self.assertEqual(json.loads(emitted), record)

    def test_nonzero_exit_retains_bounded_tails_and_waited_child_cpu(self):
        records = []
        result = subprocess.CompletedProcess(['fixture'], 7, 'x'*4000, 'y'*4000)
        before = os.times_result((0, 0, 2, 3, 0))
        after = os.times_result((0, 0, 6, 5, 0))
        with patch.object(self.module.subprocess, 'run', return_value=result) as invoked, \
                patch.object(self.module.os, 'times', side_effect=[before, after]), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError):
                self.module.run(['fixture'], observations=records)
        invoked.assert_called_once_with(['fixture'], capture_output=True, text=True,
                                        timeout=600)
        self.assertEqual(records[0]['returncode'], 7)
        self.assertFalse(records[0]['success'])
        self.assertFalse(records[0]['timedOut'])
        self.assertEqual(records[0]['stdoutTail'], 'x'*3000)
        self.assertEqual(records[0]['stderrTail'], 'y'*3000)
        self.assertEqual(records[0]['waitedChildUserCpuSeconds'], 4)
        self.assertEqual(records[0]['waitedChildSystemCpuSeconds'], 2)

    def test_success_keeps_output_and_original_deadline(self):
        records = []
        result = subprocess.CompletedProcess(['fixture'], 0, 'retained output', '')
        with patch.object(self.module.subprocess, 'run', return_value=result) as invoked, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.module.run(['fixture'], observations=records),
                             'retained output')
        invoked.assert_called_once_with(['fixture'], capture_output=True, text=True,
                                        timeout=600)
        self.assertTrue(records[0]['success'])
        self.assertFalse(records[0]['timedOut'])

    def test_binary_partial_timeout_output_is_bounded_and_decoded(self):
        records = []
        failure = subprocess.TimeoutExpired(['fixture'], 600,
                                            output=b'x'*4000+b'\xff', stderr=b'partial')
        with patch.object(self.module.subprocess, 'run', side_effect=failure) as invoked, \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(subprocess.TimeoutExpired) as caught:
                self.module.run(['fixture'], observations=records)
        self.assertIs(caught.exception, failure)
        self.assertEqual(invoked.call_count, 1)
        self.assertEqual(len(records[0]['stdoutTail']), 3000)
        self.assertTrue(records[0]['stdoutTail'].endswith('\ufffd'))
        self.assertEqual(records[0]['stderrTail'], 'partial')

    def test_initialization_timeout_writes_failed_preparation_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'payload/objects').mkdir(parents=True)
            failure = subprocess.TimeoutExpired(['ostree'], 600, output=b'partial')
            # Initialization fails before OSTree.Repo is used. Keep this fixture
            # independent of optional host OSTree GI bindings.
            with patch.object(self.module.gi, 'require_version') as require_version, \
                    patch.dict(sys.modules, {'gi.repository': SimpleNamespace(OSTree=object())}), \
                    patch.object(self.module, 'public_key', return_value=b'pinned key'), \
                    patch.object(self.module.subprocess, 'run', side_effect=failure), \
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(subprocess.TimeoutExpired):
                    self.module.bundle(root/'payload', root/'output', 'x86_64')
            require_version.assert_called_once_with('OSTree', '1.0')
            report = json.loads((root/'output/preparation.json').read_text())
            self.assertFalse(report['payloadIntegrityVerified'])
            self.assertFalse(report['packageInstalled'])
            self.assertFalse(report['packageLaunched'])
            self.assertEqual(report['bundles'], {})
            self.assertEqual(len(report['commands']), 1)
            self.assertTrue(report['commands'][0]['timedOut'])
            self.assertEqual(report['commands'][0]['timeoutSeconds'], 600)
            self.assertIn('timed out', report['error'])


if __name__ == "__main__":
    unittest.main()
