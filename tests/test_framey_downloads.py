"""Pinned Download All queue access and the real CEF/iframe bridge contracts."""
import sandbox  # noqa: F401
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ui'))
import framey_panel
import server

DIGEST = framey_panel.frame_decky_store.DOWNLOAD_ALL_DIGEST


class Downloads(unittest.TestCase):
    def test_cef_and_iframe_behavior(self):
        for name in ('framey_downloads.mjs','framey_download_parent.mjs'):
            with self.subTest(script=name):
                result = subprocess.run(['node', str(Path(__file__).parent/'page'/name)],
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_receipt_shim_actions_and_arguments_are_checked_before_cef(self):
        installed = {'storeId':131, 'sha256':DIGEST, 'compatShims':['download-all-local-queue']}
        def ssh(command, stdin, **_):
            self.assertEqual(command, 'python3 -')
            compile(stdin, '<download bridge>', 'exec')
            self.assertIn('RegisterForDownloadItems', stdin)
            self.assertNotIn('__FRAMEY_STEAM_', stdin)
            return '{"result":{"ready":false,"items":[]}}'
        with patch.object(framey_panel.frame_decky, 'plugin_status', return_value={'plugins':[installed]}):
            for action, appids, revision in [('read',None,None),('queue',[10,20],1),('close',None,None)]:
                self.assertIn('result',framey_panel.downloads(ssh,131,'panel-1',action,appids,revision,DIGEST))
            invalid = [(True,'panel-1','read',None,None,DIGEST),(14,'panel-1','read',None,None,DIGEST),
                       (131,'bad session','read',None,None,DIGEST),(131,'panel-1','ShutdownPC',None,None,DIGEST),
                       (131,'panel-1','queue',[True],1,DIGEST),(131,'panel-1','queue',[],1,DIGEST),
                       (131,'panel-1','queue',[10,10],1,DIGEST),(131,'panel-1','queue',['10'],1,DIGEST),
                       (131,'panel-1','queue',[2**32],1,DIGEST),(131,'panel-1','read',[10],None,DIGEST),
                       (131,'panel-1','queue',[10],None,DIGEST),(131,'panel-1','queue',[10],True,DIGEST),
                       (131,'panel-1','read',None,None,'a'*64)]
            for args in invalid:
                with self.subTest(args=args), self.assertRaises(framey_panel.PanelError):
                    framey_panel.downloads(lambda *_a,**_k:self.fail('Invalid request reached CEF'),*args)
            installed['compatShims'] = []
            with self.assertRaisesRegex(framey_panel.PanelError, 'reinstall'):
                framey_panel.downloads(ssh,131,'panel-1','read',receipt=DIGEST)
            installed['sha256'] = 'b'*64
            with self.assertRaisesRegex(framey_panel.PanelError, 'changed'):
                framey_panel.downloads(ssh,131,'panel-1','close',receipt=DIGEST)

    def test_facade_is_only_enabled_for_the_exact_official_plugin(self):
        with patch.object(framey_panel, '_owned_dist', return_value=(None,b'export default()=>null',DIGEST)):
            self.assertIn(b'data-downloads="1"',framey_panel.panel(131))
            self.assertNotIn(b'data-downloads=',framey_panel.panel(14))
        with patch.object(framey_panel, '_owned_dist', return_value=(None,b'export default()=>null','a'*64)):
            self.assertNotIn(b'data-downloads=',framey_panel.panel(131))

    def test_endpoint_requires_headset_runtime_and_forwards_the_pinned_receipt(self):
        with patch.object(server,'HEADSET_RUNTIME',False), patch.dict(server.os.environ,{'FRAME_E2E_CONTAINER':'0'}):
            with self.assertRaises(server.Failure):server.framey_downloads_action({})
        with patch.object(server,'HEADSET_RUNTIME',True), patch.object(framey_panel,'downloads',return_value={'result':None}) as call:
            server.framey_downloads_action({'id':131,'session':'one','action':'queue','appids':[10],'revision':1,'receipt':DIGEST})
            call.assert_called_once_with(server.ssh,131,'one','queue',[10],1,DIGEST)
