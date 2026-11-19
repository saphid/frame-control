"""Before-import observations stay bounded and identify disposable children."""
import ast
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import io
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'tests/decky-runtime/terminal_lifecycle.py'

def reader():
    node = next(node for node in ast.parse(SOURCE.read_bytes()).body
                if isinstance(node, ast.FunctionDef) and node.name == 'startup_processes')
    scope = dict(Path=Path, time=time)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), 'exec'), scope)
    return scope['startup_processes']

def fake(root, pid, parent=1, *, start=40, user=17, system=5, children=''):
    directory = root/str(pid)
    (directory/'task'/str(pid)).mkdir(parents=True, exist_ok=True)
    fields = ['0']*21
    for index,value in {0:'S',1:parent,11:user,12:system,17:1,19:start}.items():
        fields[index] = str(value)
    (directory/'stat').write_text(str(pid)+' (private name ) with spaces) '+' '.join(fields)+'\n')
    (directory/'task'/str(pid)/'children').write_text(children)
    return directory

class StartupProcessTests(unittest.TestCase):
    def test_identities_cpu_and_descendants_exclude_unrelated_processes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fake(root, 101, children='102 103 ')
            fake(root, 102, 101, user=33, children='104 ')
            fake(root, 103, 999)
            fake(root, 104, 102, system=22)
            result = reader()(101, proc_root=root)
        self.assertEqual([row['pid'] for row in result['processes']], [101,102,104])
        self.assertEqual(result['processes'][1]['userTicks'], 33)
        self.assertEqual(result['processes'][2]['systemTicks'], 22)
        self.assertFalse(result['truncated'])
        self.assertNotIn('private name', repr(result))

    def test_large_tree_is_clipped_to_sixteen_processes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fake(root, 101, children=' '.join(str(i) for i in range(102,142)))
            for pid in range(102,142): fake(root,pid,101)
            result = reader()(101, proc_root=root)
        self.assertEqual(len(result['processes']), 16)
        self.assertTrue(result['truncated'])

    def test_cycles_and_disappearing_children_do_not_repeat_or_block(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            fake(root,101,children='101 102 999')
            fake(root,102,101,children='101')
            result=reader()(101,proc_root=root)
        self.assertEqual([r['pid'] for r in result['processes']], [101,102])
        self.assertEqual(result['unavailable'], [dict(pid=999,errorType='FileNotFoundError')])

    def test_oversized_malformed_and_absent_records_return_only_error_type(self):
        for raw in (b'x'*4097,b'private malformed record',b'\xff'):
            with self.subTest(rawSize=len(raw)), tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary)
                directory=fake(root,101)
                (directory/'stat').write_bytes(raw)
                result=reader()(101,proc_root=root)
                self.assertEqual(result['processes'], [])
                self.assertNotIn('private',repr(result))
                self.assertIn('errorType',result['unavailable'][0])

    def test_identity_change_during_read_drops_the_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            directory=fake(root,101)
            old=(directory/'stat').read_bytes()
            fake(root,101,start=99)
            new=(directory/'stat').read_bytes()
            original=Path.open
            for sequence in ([old,old,new],[old,new,new]):
                remaining=list(sequence)
                def opened(path,*args,**kwargs):
                    if path==directory/'stat': return io.BytesIO(remaining.pop(0))
                    return original(path,*args,**kwargs)
                with patch.object(Path,'open',opened):
                    result=reader()(101,proc_root=root)
                self.assertEqual(result['processes'],[])
                self.assertTrue(result['identityChanged'])

    def test_oversized_children_are_refused_and_no_environment_is_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            directory=fake(root,101,children='1 '*3000)
            result=reader()(101,proc_root=root)
        self.assertEqual([row['pid'] for row in result['processes']],[101])
        self.assertEqual(result['processes'][0]['unavailableTaskChildLists'],
                         [dict(tid=101,errorType='ValueError')])

    def test_children_forked_by_non_leader_threads_are_included(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            directory=fake(root,101)
            (directory/'task/105').mkdir()
            (directory/'task/105/children').write_text('102')
            fake(root,102,101)
            result=reader()(101,proc_root=root)
        self.assertEqual([row['pid'] for row in result['processes']],[101,102])
        self.assertEqual(result['processes'][0]['taskChildListsObserved'],2)
        self.assertFalse(result['processes'][0]['taskListsTruncated'])

    def test_thread_scan_is_bounded_and_reports_incomplete_coverage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            directory=fake(root,101)
            for tid in range(200,240):
                (directory/'task'/str(tid)).mkdir()
                (directory/'task'/str(tid)/'children').write_text('')
            result=reader()(101,proc_root=root)
        self.assertTrue(result['truncated'])
        self.assertEqual(result['processes'][0]['taskChildListsObserved'],16)
        self.assertTrue(result['processes'][0]['taskListsTruncated'])

    def test_unavailable_thread_details_are_capped_without_inventing_coverage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            directory=fake(root,101)
            for tid in range(200,215): (directory/'task'/str(tid)).mkdir()
            result=reader()(101,proc_root=root)
        row=result['processes'][0]
        self.assertEqual(row['taskChildListsObserved'],1)
        self.assertEqual(row['unavailableTaskChildListCount'],15)
        self.assertEqual(len(row['unavailableTaskChildLists']),4)
        self.assertTrue(row['unavailableTaskChildListsTruncated'])

    def test_uid_change_during_read_drops_identity_and_foreign_child_is_excluded(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            directory=fake(root,101,children='102')
            child=fake(root,102,101)
            original=Path.stat
            for target,sequence in ((directory,[20,20,21]),(child,[21])):
                values=list(sequence)
                def observed(path,*args,**kwargs):
                    if path==target:return SimpleNamespace(st_uid=values.pop(0))
                    if path==directory:return SimpleNamespace(st_uid=20)
                    return original(path,*args,**kwargs)
                with patch.object(Path,'stat',observed):
                    result=reader()(101,proc_root=root)
                self.assertEqual([row['pid'] for row in result['processes']],
                                 [] if target==directory else [101])
                if target==directory:self.assertTrue(result['identityChanged'])

    def test_permission_error_does_not_retain_private_exception_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            directory=fake(root,101)
            original=Path.open
            def denied(path,*args,**kwargs):
                if path==directory/'stat':raise PermissionError('private message')
                return original(path,*args,**kwargs)
            with patch.object(Path,'open',denied):
                result=reader()(101,proc_root=root)
        self.assertEqual(result['processes'],[])
        self.assertEqual(result['unavailable'],[dict(pid=101,errorType='PermissionError')])
        self.assertNotIn('private',repr(result))
        self.assertGreaterEqual(result['finishedMonotonicNs'],result['observedMonotonicNs'])

    @unittest.skipUnless(sys.platform.startswith('linux'), 'requires Linux procfs')
    def test_real_thread_owned_child_and_cpu_delta_are_observed(self):
        import select
        source = '''import subprocess,sys,threading,time
ready=threading.Event()
stop=threading.Event()
def worker():
 child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(20)'])
 try:
  print(child.pid,flush=True)
  ready.set()
  stop.wait(10)
 finally:
  child.terminate()
  child.wait(timeout=3)
thread=threading.Thread(target=worker)
thread.start()
try:
 ready.wait(3)
 for command in sys.stdin:
  if command.strip()!='work': break
  deadline=time.process_time()+.15
  while time.process_time()<deadline: pass
  print('done',flush=True)
finally:
 stop.set()
 thread.join(3)
'''
        process=subprocess.Popen([sys.executable,'-u','-c',source],stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            self.assertTrue(select.select([process.stdout],[],[],3)[0])
            child_pid=int(process.stdout.readline())
            first=reader()(process.pid)
            rows={row['pid']:row for row in first['processes']}
            self.assertIn(child_pid,rows)
            self.assertEqual(rows[child_pid]['ppid'],process.pid)
            self.assertGreaterEqual(rows[process.pid]['taskChildListsObserved'],2)
            process.stdin.write('work\n')
            process.stdin.flush()
            self.assertTrue(select.select([process.stdout],[],[],3)[0])
            self.assertEqual(process.stdout.readline().strip(),'done')
            second=reader()(process.pid)
            after=next(row for row in second['processes'] if row['pid']==process.pid)
            before=rows[process.pid]
            self.assertEqual(after['startTicks'],before['startTicks'])
            self.assertGreater(after['userTicks']+after['systemTicks'],
                               before['userTicks']+before['systemTicks'])
            self.assertIsNone(process.poll())
        finally:
            try:
                process.communicate('stop\n',timeout=4)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=3)
            self.assertEqual(process.returncode,0)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'requires Linux procfs')
    def test_real_owned_child_identity_and_cpu_are_observed_without_signalling(self):
        child=subprocess.Popen([sys.executable,'-c', 'import time; time.sleep(10)'],
                               stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            one=reader()(os.getpid())
            rows={row['pid']:row for row in one['processes']}
            self.assertIn(child.pid,rows)
            self.assertEqual(rows[child.pid]['ppid'],os.getpid())
            self.assertEqual(rows[child.pid]['uid'],os.getuid())
            self.assertGreater(rows[child.pid]['startTicks'],0)
            self.assertIsNone(child.poll())
            two=reader()(os.getpid())
            after=next(row for row in two['processes'] if row['pid']==child.pid)
            self.assertEqual(after['startTicks'],rows[child.pid]['startTicks'])
            self.assertGreaterEqual(after['userTicks'],rows[child.pid]['userTicks'])
            self.assertGreaterEqual(after['systemTicks'],rows[child.pid]['systemTicks'])
            self.assertIsNone(child.poll())
        finally:
            child.terminate()
            child.wait(timeout=3)

if __name__=='__main__':
    unittest.main()
