// Run the real doctor page script with a minimal DOM; no browser or hardware I/O.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
class Element {
  constructor(tag) { this.tagName = tag.toUpperCase(); this.children = []; this.value = ''; this.hidden = false; this.disabled = false; this.textContent = ''; }
  append(...nodes) { this.children.push(...nodes); }
  prepend(...nodes) { this.children.unshift(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  get firstChild() { return this.children[0]; }
  get options() { return this.children; }
}
const ids = ['back','inventory','diagnose','device','message','results','json','reportSection','selection','download','copy'];
const elements = Object.fromEntries(ids.map(id => [id,new Element(id === 'device' ? 'select' : 'div')]));
const requests = [];
let pending;
const context = vm.createContext({
  document:{getElementById:id=>elements[id],createElement:tag=>new Element(tag)},
  URLSearchParams,location:{search:'?key=test-key'},
  fetch:(path,options)=>{ requests.push({path,options}); return new Promise(resolve=>{pending=resolve;}); },
  navigator:{clipboard:{writeText:async()=>{throw Error('clipboard denied');}}},
});
const source = readFileSync(new URL('../../ui/wireless-doctor.html',import.meta.url),'utf8');
vm.runInContext(source.match(/<script>([\s\S]*)<\/script>/)[1],context);
assert.equal(requests.length,0,'opening the page must not probe');
assert.equal(elements.back.href,'/?key=test-key#devices');
const fixture = {
  schema:1,supported:true,selected:null,
  usb:[{id:'usb:1-2',vid:'1234',pid:'5678',product:'<img src=x onerror=alert(1)>'}],
  interfaces:[{id:'net:wlan0',name:'wlan0',usb:'usb:1-2',driver:'synthetic'}],
  checks:[{id:'presence',title:'Presence',status:'ok',suggestion:'Select hardware',evidence:['Synthetic evidence']}]
};
let promise=elements.inventory.onclick();
assert.equal(elements.device.disabled,true,'selection must stay fixed during a read');
assert.equal(requests[0].path,'/api/wireless-doctor');
assert.equal(requests[0].options.headers['X-Frame-UI'],'test-key');
pending({ok:true,json:async()=>fixture}); await promise;
assert.equal(elements.device.value,'','no automatic hardware choice');
assert.equal(elements.diagnose.disabled,true);
assert.equal(elements.device.options.length,3);
assert.match(elements.device.options[2].textContent,/<img src=x/,'hardware labels must stay plain text');
assert.equal(elements.device.options[2].children.length,0);
assert.equal(elements.reportSection.hidden,false);
assert.equal(elements.results.children.length,1);
elements.device.value='net:wlan0'; elements.device.onchange();
assert.equal(elements.diagnose.disabled,false);
assert.equal(elements.results.children.length,0,'changing hardware clears the previous result');
assert.equal(elements.reportSection.hidden,true,'cannot export an old report for a new selection');
promise=elements.diagnose.onclick();
assert.equal(requests[1].path,'/api/wireless-doctor?device=net%3Awlan0');
assert.equal(elements.device.disabled,true);
pending({ok:true,json:async()=>({...fixture,selected:'net:wlan0'})}); await promise;
assert.equal(elements.device.value,'net:wlan0');
assert.equal(elements.device.disabled,false);
await elements.copy.onclick();
assert.match(elements.message.textContent,/Clipboard unavailable/);
promise=elements.diagnose.onclick();
assert.equal(elements.results.children.length,0,'clear a healthy snapshot before retrying');
assert.equal(elements.reportSection.hidden,true);
pending({ok:false,json:async()=>({error:'Device is no longer present. Refresh and select an observed device.'})}); await promise;
assert.match(elements.message.textContent,/no longer present/);
assert.equal(elements.results.children.length,0);
assert.equal(elements.reportSection.hidden,true,'failed requests cannot export stale success');
assert.equal(elements.inventory.disabled,false,'can refresh after failure');
promise=elements.inventory.onclick();
pending({ok:true,json:async()=>({...fixture,supported:false,usb:[],interfaces:[]})}); await promise;
assert.equal(elements.selection.hidden,true);
assert.equal(elements.diagnose.disabled,true);
assert.match(elements.message.textContent,/only on a Linux PC/);
console.log('doctor UI: on-demand reads, explicit selection, safe labels, stale report clearing and failure recovery passed');
