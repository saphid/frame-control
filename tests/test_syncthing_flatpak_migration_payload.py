"""Migration must load the delivered backend without the checkout on sys.path."""
import ast
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == 'linux', 'Candidate backend uses Linux process and flock APIs')
class MigrationPayload(unittest.TestCase):
    def test_installed_backend_imports_its_real_ipc_adapter(self):
        source = ROOT / 'tests/decky-runtime/syncthing_migration.py'
        tree = ast.parse(source.read_text())
        main = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == 'main')
        setup = next(node for node in main.body if isinstance(node, ast.Try)).body
        start = next(index for index, node in enumerate(setup)
                     if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                     and ast.unparse(node.value.func) == 'shutil.copy')
        end = next(index for index, node in enumerate(setup)
                   if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == 'settings_path'
                           for target in node.targets))
        delivery = ast.Module(body=setup[start:end], type_ignores=[])
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            plugin = base / 'decky-syncthing'
            (plugin / 'bin').mkdir(parents=True)
            inputs = base / 'input'
            inputs.mkdir()
            shutil.copy(ROOT / 'ui/vendor/syncthing-0.2.7/main.py', inputs / 'main.py')
            shutil.copy(ROOT / 'ui/framey_decky_ipc.py', inputs / 'framey_decky_ipc.py')
            (inputs / 'watchdog').write_bytes(b'private fixture; never executed\n')

            class OwnedInputs(ast.NodeTransformer):
                def visit_Constant(self, node):
                    if isinstance(node.value, str) and node.value.startswith('/input/'):
                        return ast.copy_location(ast.Constant(str(inputs / node.value[7:])), node)
                    return node

            delivery = ast.fix_missing_locations(OwnedInputs().visit(delivery))
            exec(compile(delivery, str(source), 'exec'), dict(shutil=shutil, plugin=plugin))
            # Isolate imports from PYTHONPATH, test stubs and the source checkout.
            # Only Decky's provided API is a fixture; both shipped Python files
            # are real and resolved from the installed plugin directory.
            probe = '''
import logging, pathlib, runpy, sys, types
plugin = pathlib.Path(sys.argv[1])
sys.path[:0] = [str(plugin), str(plugin / 'py_modules')]
decky = types.ModuleType('decky_plugin')
decky.logger = logging.getLogger('private-migration-import')
for name in ('DIR', 'SETTINGS_DIR', 'RUNTIME_DIR', 'LOG_DIR'):
    setattr(decky, 'DECKY_PLUGIN_' + name, str(plugin))
sys.modules['decky_plugin'] = decky
class UnixSocket:
    async def _read_single_line(self, reader): pass
    async def _listen_for_method_call(self, reader, writer): pass
module = types.ModuleType('decky_loader.localplatform.localsocket')
module.UnixSocket = UnixSocket
sys.modules[module.__name__] = module
backend = runpy.run_path(str(plugin / 'main.py'))
assert backend['Plugin']
import framey_decky_ipc
assert pathlib.Path(framey_decky_ipc.__file__).resolve() == plugin / 'py_modules/framey_decky_ipc.py'
assert UnixSocket._read_single_line.__module__ == 'framey_decky_ipc'
print('Installed migration backend and real IPC adapter loaded')
'''
            result = subprocess.run([sys.executable, '-I', '-c', probe, str(plugin)],
                                    cwd=base, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
