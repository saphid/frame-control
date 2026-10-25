import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const html = readFileSync(new URL('../../ui/headset.html', import.meta.url), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1].split('refresh();refreshGames();')[0];
class Element {
  constructor(id='') {this.id=id; this.value=''; this.textContent=''; this.children=[]; this.disabled=false; this.hidden=false;}
  append(...nodes) {this.children.push(...nodes);}
  replaceChildren(...nodes) {this.children=nodes; this.textContent='';}
  scrollIntoView() {}
  removeAttribute(name) {delete this[name];}
}
const elements = new Map();
elements.set('deckyStoreFilter',Object.assign(new Element('deckyStoreFilter'),{value:'all'}));
const document = {getElementById(id) {if(!elements.has(id)) elements.set(id,new Element(id)); return elements.get(id);},
  createElement() {return new Element();}, hidden:false};
const session = new Map();
const ctx = vm.createContext({document, location:{hash:'',pathname:'/'},
  sessionStorage:{getItem:key=>session.get(key)||'',setItem:(key,value)=>session.set(key,value),removeItem:key=>session.delete(key)},
  history:{replaceState(){}}, confirm:()=>true,
  window:{addEventListener(){}}, setInterval(){}, setTimeout(){},
  fetch(){throw Error('No network expected');}, console});
vm.runInContext(script,ctx);
const el=id=>document.getElementById(id);
const fixtures=Array.from({length:43},(_,i)=>({id:i+1,name:`Plugin ${i+1}`,author:i===42?'Special Author':'Maker',
  description:'A panel',version:'1.0',root:i===0}));
ctx.fixtures=fixtures;
vm.runInContext('deckyStore=fixtures; deckyState={running:true,plugins:[{storeId:2,version:"1.0"}]}; showDeckyStore()',ctx);
assert.equal(el('deckyStoreSummary').textContent,'43 plugins found');
assert.equal(el('deckyStoreList').children.length,20);
assert.equal(el('deckyStorePage').textContent,'Page 1 of 3');
el('deckyStoreNext').onclick();
assert.equal(el('deckyStoreList').children.length,20);
el('deckyStoreNext').onclick();
assert.equal(el('deckyStoreList').children.length,3);
assert.equal(el('deckyStoreNext').disabled,true);
el('deckySearch').value='special author'; el('deckySearch').oninput();
assert.equal(el('deckyStoreSummary').textContent,'1 plugin found');
assert.match(el('deckyStoreList').children[0].children[0].textContent,/Plugin 43/);
assert.equal(el('deckyStorePage').textContent,'Page 1 of 1');
el('deckySearch').value=''; el('deckyStoreFilter').value='installed'; el('deckyStoreFilter').onchange();
assert.equal(el('deckyStoreSummary').textContent,'1 plugin found');
assert.match(el('deckyStoreList').children[0].children[0].textContent,/Plugin 2/);
el('deckyStoreFilter').value='compatible'; el('deckyStoreFilter').onchange();
assert.equal(el('deckyStoreSummary').textContent,'42 plugins found');
el('deckySearch').value='no matching plugin'; el('deckySearch').oninput();
assert.equal(el('deckyStoreList').textContent,'No plugins match this search.');

// The page polls the actual job endpoint and keeps a separate visible result.
ctx.mockApi=async path => {
  if(path==='/api/decky/plugin')return {job:'job-1'};
  if(path.startsWith('/api/job'))return {done:true,message:'Installed Plugin 2'};
  if(path==='/api/decky')return {running:true,plugins:[{storeId:2,name:'Plugin 2',version:'1.0'}]};
  throw Error(`unexpected ${path}`);
};
vm.runInContext('api=mockApi',ctx);
await vm.runInContext('deckyChange("install",{id:2,name:"Plugin 2"})',ctx);
assert.equal(el('deckyJobStatus').textContent,'Installed Plugin 2');
assert.equal(el('deckyJobProgress').value,100);
assert.equal(el('deckyJobCheck').hidden,true);
assert.equal(session.has('frameyPluginJob'),false);
// A stopped Decky service must still offer recovery by removing its owned plugin.
ctx.mockApi=async path => path==='/api/decky' ?
  {managed:true,running:false,plugins:[{storeId:2,name:'Plugin 2',version:'1.0'}]} :
  Promise.reject(Error(`unexpected ${path}`));
vm.runInContext('api=mockApi',ctx);
await vm.runInContext('refreshDecky()',ctx);
assert.equal(el('deckyInstalled').children[0].children[2].disabled,false);
el('deckySearch').value='';el('deckyStoreFilter').value='all';
vm.runInContext('showDeckyStore()',ctx);
assert.equal(el('deckyStoreList').children[1].children[1].disabled,true);
ctx.mockApi=async path => {
  if(path==='/api/decky/plugin')return {job:'job-2'};
  if(path.startsWith('/api/job'))return {done:true,error:'archive digest mismatch'};
  if(path==='/api/decky')return {running:true,plugins:[]};
  throw Error(`unexpected ${path}`);
};
vm.runInContext('api=mockApi',ctx);
await vm.runInContext('deckyChange("update",{id:2,name:"Plugin 2"})',ctx);
assert.match(el('deckyJobStatus').textContent,/Error: archive digest mismatch/);
assert.equal(session.has('frameyPluginJob'),false);
