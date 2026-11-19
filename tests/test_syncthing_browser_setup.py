"""Exercise the actual private DOM driver, including manual setup controls."""
import ast
import json
from pathlib import Path
import shutil
import subprocess
import unittest

DRIVER = r'''const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const {source,mode}=JSON.parse(fs.readFileSync(0,'utf8'));
let listener,now=0,state='welcome',value='',savedKey='',savedPort='',typed=[];
const messages=[],timers=[];
const manualPort=mode.includes('port'),manualKey=mode.includes('key');
const fixtureKey='synthetic-owned-fixture-key';
const afterPort=()=>state=manualKey?'key':'almost';
const input={dispatchEvent(event){typed.push(event.type);}};
const text=()=>({welcome:'Start Setup',install:'Installation Method',port:'Please enter the web UI port',
 key:'API Key The API key for Syncthing\'s API could not be detected. Please enter the currently configured API key.',
 almost:'Almost done!',finish:'All done!',running:'Running\nPrivate service sync\nowned-peer'})[state];
const buttons=()=>{
 if(state==='welcome')return [{textContent:'Start Setup',click(){state='install';}}];
 if(state==='install')return [{textContent:'"Syncthing GTK" Flatpak',click(){if(manualPort)state='port';else afterPort();}}];
 if(state==='port')return [{textContent:'Continue',click(){savedPort=value;value='';afterPort();}}];
 if(state==='key')return [{textContent:'Continue',click(){savedKey=value;value='';state='almost';}}];
 if(state==='almost')return [{textContent:'Continue',click(){state='finish';}}];
 if(state==='finish')return [{textContent:'Get Started',click(){state='running';}}];
 return [];
};
function HTMLInputElement(){};
Object.defineProperty(HTMLInputElement.prototype,'value',{set(v){value=v;}});
const context={Date:{now:()=>now},HTMLInputElement,Event:function(type){this.type=type;},
 addEventListener(type,callback){if(type==='message')listener=callback;},
 document:{getElementById(){return {innerText:text()};},querySelectorAll(){return buttons();},querySelector(){return input;}},
 parent:{postMessage(message){messages.push(message);}},
 setTimeout(callback,delay){timers.push({callback,delay});}
};context.window=context;
vm.runInNewContext(source,context);
(async()=>{
 const pending=listener({source:context.parent,data:{type:'test:advance',action:'setup',apiKey:mode==='missing-key'?undefined:fixtureKey}});
 for(let i=0;i<200;i++){
  for(let j=0;j<12;j++)await Promise.resolve();
  if(messages.some(m=>m.type==='test:stage'))break;
  const timer=timers.shift();assert(timer,'driver stalled without a bounded timer');
  now+=timer.delay===50?50:60001;timer.callback();
 }
 await pending;
 const stage=messages.find(m=>m.type==='test:stage'),failure=messages.find(m=>m.type==='test:failure');
 if(mode==='missing-key'){
  assert.equal(stage.stage,'failed');assert.match(failure.error,/private fixture API key/);
  assert.equal(savedKey,'');assert(!typed.length,'missing key must not type or submit');
 }else{
  assert(!failure, failure?.error);assert.equal(stage.stage,'running');
  assert.equal(stage.manualApiKeyFallbackUsed,manualKey);
  assert.equal(stage.manualPortFallbackUsed,manualPort);
  assert.equal(savedKey,manualKey?fixtureKey:'');assert.equal(savedPort,manualPort?'8384':'');
  assert.equal(typed.length,(Number(manualPort)+Number(manualKey))*2);
  assert.equal(JSON.stringify(messages).includes(fixtureKey),false,'evidence must not expose fixture key');
 }
 console.log(JSON.stringify({mode,stage:stage.stage,manualApiKeyFallbackUsed:stage.manualApiKeyFallbackUsed,
  enteredExpectedKey:savedKey===fixtureKey,keyAbsentFromEvidence:!JSON.stringify(messages).includes(fixtureKey)}));
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
'''

@unittest.skipUnless(shutil.which('node'), 'Node is needed for the actual DOM-driver check')
class BrowserManualSetup(unittest.TestCase):
    def exercise(self, mode):
        source=Path(__file__).parent/'decky-runtime/syncthing_browser.py'
        tree=ast.parse(source.read_text())
        probe=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
                   and any(isinstance(t,ast.Name) and t.id=='PROBE' for t in n.targets))
        run=subprocess.run(['node','-e',DRIVER],input=json.dumps(dict(source=probe,mode=mode)),
                           text=True,capture_output=True,timeout=8)
        self.assertEqual(run.returncode,0,run.stderr)
        return json.loads(run.stdout)

    def test_automatic_key_discovery_is_distinguished_from_manual_entry(self):
        self.exercise('automatic')

    def test_manual_key_form_uses_the_expected_private_fixture_value(self):
        self.exercise('key')

    def test_manual_port_and_key_forms_both_complete_through_inputs(self):
        self.exercise('port-key')

    def test_missing_fixture_key_refuses_manual_form_submission(self):
        self.exercise('missing-key')

if __name__=='__main__':
    unittest.main()
