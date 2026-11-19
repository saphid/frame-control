"""Removal evidence must follow a render opportunity and retain failure controls.

This schedules the actual private browser PROBE in a controlled event loop.
It does not reproduce a hosted compositor failure or qualify VR rendering.
"""
import ast
import json
from pathlib import Path
import shutil
import subprocess
import unittest


DRIVER = r''''use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const source = input.source;
const mode = input.mode;
const events = [], messages = [], frames = [], timers = [];
let listener, now = 0, domRows = ['owned-terminal'], paintedRows = ['owned-terminal'];
let inList = false;
const back = {textContent: 'Back to plugin', click() {inList = true;}};
const remove = {click() {if(mode !== 'never-removed') domRows = [];}};
const sectionButtons = () => inList && domRows.length ? [{}, remove] : [];
const context = {
  Date: {now: () => now},
  addEventListener(type, callback) {if(type === 'message') listener = callback;},
  document: {
    getElementById() {return {innerText: domRows.length ? 'Add Terminal Active Terminals owned-terminal' : 'Add Terminal Active Terminals'};},
    querySelectorAll(selector) {return selector === 'section button' ? sectionButtons() : [back];},
    querySelector() {return null;}
  },
  parent: {postMessage(payload) {messages.push(payload);events.push({type:payload.type,stage:payload.stage,paintedRows:[...paintedRows]});}},
  requestAnimationFrame(callback) {frames.push(callback);},
  setTimeout(callback, delay) {timers.push({callback, delay});}
};
vm.runInNewContext(source, context);
const drain = async () => {for(let i=0;i<12;i++) await Promise.resolve();};
const stage = () => messages.find(x => x.type === 'test:stage');
const fail = () => messages.find(x => x.type === 'test:failure');
(async () => {
  const pending = listener({source:context.parent, data:{type:'test:advance',action:'close'}});
  await drain();
  if(mode === 'never-removed') {
    assert(!stage() && !fail());
    assert.equal(timers.length, 1);
    now = 60_001; timers.shift().callback();await drain();await pending;
    assert(!stage());assert.match(fail().error, /Terminal DOM timed out/);
    assert.equal(fail().diagnostic.phase, 'terminal-list-after-remove');
    assert.equal(frames.length, 0);
    console.log(JSON.stringify({mode,domTimeoutPreserved:true,noRemovedStage:true,framesRequested:0}));return;
  }
  assert(!stage(), 'removed evidence was emitted while the previous terminal row was still painted');
  assert(!fail());assert.equal(frames.length, 1);
  frames.shift()(16);paintedRows = [...domRows];await drain();
  assert(!stage(), 'removed evidence was emitted before the second render opportunity');
  assert.equal(frames.length, 1);
  if(mode === 'reappeared') domRows = ['unexpected-terminal'];
  frames.shift()(32);paintedRows = [...domRows];await drain();await pending;
  if(mode === 'reappeared') {
    assert(!stage());assert.match(fail().error, /Terminal list changed before removed capture/);
    console.log(JSON.stringify({mode,reappearedRowsRefused:true,noRemovedStage:true}));return;
  }
  assert(!fail());assert.equal(stage().stage, 'removed');
  assert.equal(stage().errors.length, 0);assert.equal(paintedRows.length, 0);
  assert.equal(events.length, 1);assert.equal(events[0].paintedRows.length, 0);
  console.log(JSON.stringify({mode,removedAfterPaint:true,framesObserved:2,syntheticScheduler:true,realBrowserVerified:false}));
})().catch(error => {console.error(error.stack);process.exitCode=1;});
'''


@unittest.skipUnless(shutil.which('node'), 'Node is needed for the browser scheduling check')
class TerminalRemovalPaint(unittest.TestCase):
    def exercise(self, mode):
        source = Path(__file__).parent/'decky-runtime/terminal_browser.py'
        tree = ast.parse(source.read_text())
        probe = next(ast.literal_eval(node.value) for node in tree.body
                     if isinstance(node, ast.Assign) and any(
                         isinstance(target, ast.Name) and target.id == 'PROBE'
                         for target in node.targets))
        run = subprocess.run(['node', '-e', DRIVER], input=json.dumps(dict(source=probe, mode=mode)),
                             capture_output=True, text=True, timeout=8)
        self.assertEqual(run.returncode, 0, run.stderr)
        return json.loads(run.stdout)

    def test_removed_stage_waits_for_empty_list_to_render(self):
        report = self.exercise('empty')
        self.assertIs(report['removedAfterPaint'], True)

    def test_reappeared_row_refuses_removed_evidence(self):
        report = self.exercise('reappeared')
        self.assertIs(report['reappearedRowsRefused'], True)

    def test_nonempty_list_keeps_original_timeout_and_never_stages(self):
        report = self.exercise('never-removed')
        self.assertIs(report['domTimeoutPreserved'], True)
        self.assertIs(report['noRemovedStage'], True)
