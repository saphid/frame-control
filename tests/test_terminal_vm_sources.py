"""A frozen guest must contain the local modules imported by its entry point."""
import sandbox  # noqa: F401
import ast
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('terminal_vm_sources',
    ROOT/'scripts/framey-test-terminal-browser.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class TerminalVmSources(unittest.TestCase):
    def test_entry_point_local_imports_are_in_both_guest_archives(self):
        entry = ROOT/'tests/decky-runtime/check.py'
        tree = ast.parse(entry.read_text())
        local_imports = set()
        for node in tree.body:
            names = ([v.name for v in node.names] if isinstance(node, ast.Import) else
                     [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for name in names:
                path = entry.with_name(name.split('.')[0]+'.py')
                if path.is_file():
                    local_imports.add(str(path.relative_to(ROOT)))
        self.assertIn('tests/decky-runtime/runtime_console.py', local_imports)
        for arch in ('x86_64', 'aarch64'):
            for production_http in (False, True):
                with self.subTest(arch=arch, production_http=production_http):
                    sources = set(runner.source_names(production_http, arch))
                    self.assertLessEqual(local_imports, sources)
                    self.assertTrue(all((ROOT/name).is_file() for name in sources))
