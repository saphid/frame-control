"""Private profile fixture writes keep the real watcher on a complete preset."""
import sandbox  # noqa: F401
import ast
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
tree = ast.parse((ROOT / 'tests/decky-runtime/mangopeel.py').read_text())
functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name in ('steam_profile', 'write_steam_profile')]
fixture = types.SimpleNamespace()
namespace = {'os': os}
exec(compile(ast.Module(body=functions, type_ignores=[]), 'mangopeel-fixture-writes', 'exec'), namespace)
fixture.__dict__.update(namespace)


class MangoPeelFixtureWrites(unittest.TestCase):
    def test_real_file_observer_sees_complete_profiles_on_same_inode(self):
        with tempfile.TemporaryDirectory() as folder:
            profile = Path(folder) / 'profile.conf'
            neighbor = Path(folder) / 'neighbor.conf'
            neighbor.write_bytes(b'preserve neighboring configuration\n')
            original_open = Path.open
            for index, previous in ((2, 'mangopeel_flag=1\nmangoapp_steam\nfps=1'),
                                    (3, 'mangopeel_flag=2\nmangoapp_steam\nfps=1')):
                with self.subTest(index=index):
                    profile.write_bytes(previous.encode())
                    inode = profile.stat().st_ino
                    seen = []
                    def observe():
                        with original_open(profile, 'rb') as reader:
                            seen.append(reader.read())
                    class ObservedStream:
                        def __init__(self, stream): self.stream = stream
                        def __enter__(self):
                            observe()
                            return self
                        def __exit__(self, *args): self.stream.close()
                        def fileno(self): return self.stream.fileno()
                        def write(self, data):
                            count = self.stream.write(data)
                            observe()
                            return count
                    def observed_open(path, *args, **kwargs):
                        stream = original_open(path, *args, **kwargs)
                        return ObservedStream(stream) if path == profile else stream
                    with patch.object(Path, 'open', observed_open):
                        fixture.write_steam_profile(profile, index)
                    expected = fixture.steam_profile(index).encode()
                    self.assertEqual(seen, [previous.encode(), expected])
                    self.assertEqual(profile.read_bytes(), expected)
                    self.assertEqual(profile.stat().st_ino, inode)
                    self.assertEqual(neighbor.read_bytes(), b'preserve neighboring configuration\n')

    def test_changed_larger_fixture_is_refused_without_truncating(self):
        with tempfile.TemporaryDirectory() as folder:
            profile = Path(folder) / 'profile.conf'
            original = b'preserve unexpected larger fixture' * 10
            profile.write_bytes(original)
            inode = profile.stat().st_ino
            with self.assertRaises(AssertionError):
                fixture.write_steam_profile(profile, 2)
            self.assertEqual(profile.read_bytes(), original)
            self.assertEqual(profile.stat().st_ino, inode)
