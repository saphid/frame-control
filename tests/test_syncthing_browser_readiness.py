"""Exercise the VM browser's actual startup loop without a browser or headset."""
import ast
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class BrowserReadiness(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).parent/'decky-runtime/syncthing_browser.py'
        tree = ast.parse(source.read_text())
        exercise = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'exercise')
        block = next(n for n in ast.walk(exercise) if isinstance(n, ast.With)
                     and any(isinstance(s, ast.While) for s in n.body))
        start = next(i for i, n in enumerate(block.body) if isinstance(n, ast.Assign)
                     and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'deadline')
        end = next(i for i, n in enumerate(block.body[start:], start) if isinstance(n, ast.Assert))
        wrapper = ast.parse('def wait(browser, profile, report):\n page = None\n return page').body[0]
        wrapper.body[1:1] = block.body[start:end+1]
        self.now = 0
        self.on_sleep = lambda: None
        def sleep(seconds):
            self.now += seconds
            self.on_sleep()
        self.backend = SimpleNamespace(Fail=RuntimeError, Page=Mock())
        scope = dict(time=SimpleNamespace(monotonic=lambda: self.now, sleep=sleep),
                     frame_steam=self.backend)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[])),
                     str(source), 'exec'), scope)
        self.wait = scope['wait']
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.profile = Path(self.temporary.name)
        self.port = self.profile/'DevToolsActivePort'
        self.browser = Mock(poll=lambda: None)
        self.report = {}

    def ready_page(self):
        page = Mock()
        page.eval.return_value = True
        self.backend.Page.return_value = page
        return page

    def test_empty_port_file_is_retried_until_chromium_publishes_port(self):
        self.port.touch()
        page = self.ready_page()
        self.on_sleep = lambda: self.port.write_text('12345\nfixture')
        self.assertIs(self.wait(self.browser, self.profile, self.report), page)
        self.assertGreater(self.now, 0)
        self.assertEqual(self.backend.CDP, 'http://127.0.0.1:12345/json')
        self.backend.Page.assert_called_once()

    def test_file_disappearing_during_read_is_retried(self):
        self.port.write_text('12345\nfixture')
        page = self.ready_page()
        with patch.object(Path, 'read_text', side_effect=[FileNotFoundError('port moved'), '12345\nfixture']):
            self.assertIs(self.wait(self.browser, self.profile, self.report), page)
        self.assertEqual(self.report['lastReadinessError'], 'port moved')
        self.assertGreater(self.now, 0)

    def test_permanently_empty_file_keeps_bounded_readiness_failure(self):
        self.port.touch()
        with self.assertRaisesRegex(AssertionError, 'Browser CDP/panel readiness unavailable'):
            self.wait(self.browser, self.profile, self.report)
        self.assertGreaterEqual(self.now, 60)
        self.assertLess(self.now, 61)
        self.backend.Page.assert_not_called()

    def test_exited_browser_keeps_distinct_failure(self):
        self.browser.poll = lambda: 7
        self.browser.returncode = 7
        with self.assertRaisesRegex(RuntimeError, 'Sandboxed browser exited: 7'):
            self.wait(self.browser, self.profile, self.report)
        self.assertEqual(self.now, 0)

    def test_incomplete_page_is_closed_before_ready_page_is_accepted(self):
        self.port.write_text('12345\nfixture')
        pending, ready = Mock(), Mock()
        pending.eval.side_effect = [False, ['loading']]
        ready.eval.return_value = True
        self.backend.Page.side_effect = [pending, ready]
        self.assertIs(self.wait(self.browser, self.profile, self.report), ready)
        pending.sock.close.assert_called_once()
        ready.sock.close.assert_not_called()
        self.assertEqual(self.report['startupErrors'], ['loading'])


if __name__ == '__main__':
    unittest.main()
