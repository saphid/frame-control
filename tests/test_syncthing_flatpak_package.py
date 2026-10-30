"""Prepared bundles cannot bypass exact architecture/commit/signature gates."""

import copy
import importlib.util
from pathlib import Path
import unittest


class PreparedPackage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = (
            Path(__file__).resolve().parents[1]
            / "scripts/framey-test-syncthing-flatpak-package.py"
        )
        spec = importlib.util.spec_from_file_location("flatpak_package", path)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def prepared(self, arch):
        return {
            "architecture": arch,
            "commits": self.module.COMMITS[arch],
            "keySha256": self.module.KEY_SHA256,
            "payloadIntegrityVerified": True,
            "signatures": {"app": 1, "runtime": 1},
            "bundles": {
                kind: {"commit": commit, "bytes": 100, "sha256": "a" * 64}
                for kind, commit in self.module.COMMITS[arch].items()
            },
        }

    def test_native_architecture_has_its_own_exact_commit_pins(self):
        for arch in self.module.ARCHES:
            report = self.prepared(arch)
            self.assertEqual(
                self.module.prepared_bundles(report, arch), report["bundles"]
            )
        self.assertNotEqual(
            self.module.COMMITS["x86_64"], self.module.COMMITS["aarch64"]
        )

    def test_other_architecture_or_unsigned_or_unverified_closure_is_refused(self):
        report = self.prepared("aarch64")
        mutations = [
            dict(architecture="x86_64"),
            dict(commits=self.module.COMMITS["x86_64"]),
            dict(keySha256="0" * 64),
            dict(payloadIntegrityVerified=False),
            dict(signatures={"app": 1, "runtime": 0}),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.module.prepared_bundles({**report, **mutation}, "aarch64")

    def test_mismatched_bundle_commit_and_oversized_bundle_are_refused(self):
        for kind in ("app", "runtime"):
            for mutation in (
                dict(commit="0" * 64),
                dict(bytes=0),
                dict(bytes=384 * 1024**2 + 1),
            ):
                report = copy.deepcopy(self.prepared("aarch64"))
                report["bundles"][kind].update(mutation)
                with self.subTest(kind=kind, mutation=mutation), self.assertRaises(
                    ValueError
                ):
                    self.module.prepared_bundles(report, "aarch64")

    def test_missing_bundle_is_refused(self):
        report = self.prepared("x86_64")
        del report["bundles"]["runtime"]
        with self.assertRaises(ValueError):
            self.module.prepared_bundles(report, "x86_64")


if __name__ == "__main__":
    unittest.main()
