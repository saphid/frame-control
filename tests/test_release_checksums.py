"""Checksum generator uses only complete, unambiguous GitHub asset metadata."""
import sandbox  # noqa: F401
import hashlib
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "release-checksums.py"
spec = importlib.util.spec_from_file_location("release_checksums", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Checksums(unittest.TestCase):
    def test_complete_list_matches_bytes(self):
        assets = []
        for i, name in enumerate(module.INSTALLERS):
            assets.append({"name": name, "digest": "sha256:" + hashlib.sha256(str(i).encode()).hexdigest()})
        actual = module.checksums({"assets": assets})
        self.assertEqual(len(actual.splitlines()), 10)
        self.assertEqual(actual.splitlines()[0], hashlib.sha256(b"0").hexdigest() + "  " + module.INSTALLERS[0])

    def test_missing_duplicate_and_bad_digest_fail(self):
        assets = [{"name": name, "digest": "sha256:" + "0" * 64} for name in module.INSTALLERS]
        for changed in (assets[:-1], assets + [assets[0]],
                        [dict(assets[0], digest="sha256:bad"), *assets[1:]]):
            with self.assertRaises(ValueError):
                module.checksums({"assets": changed})

    def test_tag_or_exact_untagged_draft(self):
        lines = ['{"id": 1, "tag_name": "untagged-a", "draft": true, "name": "Frame Control 9.8.7"}',
                 '{"id": 2, "tag_name": "v9.8.8", "draft": false, "name": "Frame Control 9.8.8"}']
        self.assertEqual(module.find_release(lines, "v9.8.7")["id"], 1)
        self.assertEqual(module.find_release(lines, "v9.8.8")["id"], 2)


if __name__ == "__main__":
    unittest.main()
