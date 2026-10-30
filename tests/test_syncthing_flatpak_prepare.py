"""Bounded package preparation refuses incorrect metadata and unsafe cache inputs."""

import hashlib
import importlib.util
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
