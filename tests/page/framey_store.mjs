import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
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
  crypto:webcrypto,
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
ctx.mockApi=async (path,body) => {
  if(path==='/api/decky/plugin'){assert.equal(body.sha256,'a'.repeat(64));return {job:'job-1'};}
  if(path.startsWith('/api/job'))return {done:true,message:'Installed Plugin 2'};
  if(path==='/api/decky')return {running:true,plugins:[{storeId:2,name:'Plugin 2',version:'1.0'}]};
  throw Error(`unexpected ${path}`);
};
vm.runInContext('api=mockApi',ctx);
await vm.runInContext('deckyChange("install",{id:2,name:"Plugin 2",sha256:"a".repeat(64)})',ctx);
assert.equal(el('deckyJobStatus').textContent,'Installed Plugin 2');
assert.equal(el('deckyJobProgress').value,100);
assert.equal(el('deckyJobCheck').hidden,true);
assert.equal(session.has('frameyPluginJob'),false);

// If the server accepts the POST but its response is lost, the panel already
// has the ID needed to find the job. It must not offer a second install.
let lostJobId, lostPosts=0;
ctx.mockApi=async (path,body) => {
  if(path==='/api/decky/plugin'){
    lostPosts++; lostJobId=body.requestId;
    assert.match(lostJobId,/^[0-9a-f]{32}$/);
    throw Error('POST response lost');
  }
  if(path.startsWith('/api/job')){
    assert.equal(new URL(path,'http://localhost').searchParams.get('id'),lostJobId);
    return {done:true,message:'Recovered install'};
  }
  if(path==='/api/decky')return {managed:true,running:true,plugins:[]};
  throw Error(`unexpected ${path}`);
};
vm.runInContext('api=mockApi',ctx);
await vm.runInContext('deckyChange("install",{id:2,name:"Plugin 2",sha256:"a".repeat(64)})',ctx);
assert.equal(JSON.parse(session.get('frameyPluginJob')).job,lostJobId);
assert.equal(el('deckyJobCheck').hidden,false);
await vm.runInContext('deckyChange("install",{id:2,name:"Plugin 2",sha256:"a".repeat(64)})',ctx);
assert.equal(lostPosts,1);
await vm.runInContext('checkDeckyJob()',ctx);
assert.equal(el('deckyJobStatus').textContent,'Recovered install');
assert.equal(session.has('frameyPluginJob'),false);

// A definite validation rejection never reserved a job on the server.
ctx.mockApi=async path => {
  if(path==='/api/decky/plugin'){
    const error=Error('Invalid reviewed store version');error.status=400;throw error;
  }
  if(path==='/api/decky')return {managed:true,running:true,plugins:[]};
  throw Error(`unexpected ${path}`);
};
vm.runInContext('api=mockApi',ctx);
await vm.runInContext('deckyChange("install",{id:2,name:"Plugin 2",sha256:"bad"})',ctx);
assert.equal(session.has('frameyPluginJob'),false);
assert.equal(el('deckyJobCheck').hidden,true);

// A stopped Decky service must still offer recovery by removing its owned plugin.
ctx.mockApi=async path => path==='/api/decky' ?
  {managed:true,running:false,plugins:[{storeId:2,name:'Plugin 2',version:'1.0'}]} :
  Promise.reject(Error(`unexpected ${path}`));
vm.runInContext('api=mockApi',ctx);
await vm.runInContext('refreshDecky()',ctx);
assert.equal(el('deckyInstalled').children[0].children.find(child=>child.textContent==='Remove').disabled,false);
assert.equal(el('deckyInstalled').children[0].children.find(child=>child.textContent==='Open panel').disabled,true);
el('deckySearch').value='';el('deckyStoreFilter').value='all';
vm.runInContext('showDeckyStore()',ctx);
assert.equal(el('deckyStoreList').children[1].children[1].disabled,true);
ctx.mockApi=async (path,body) => {
  if(path==='/api/decky/plugin'){assert.equal(body.sha256,'b'.repeat(64));return {job:'job-2'};}
  if(path.startsWith('/api/job'))return {done:true,error:'archive digest mismatch'};
  if(path==='/api/decky')return {running:true,plugins:[]};
  throw Error(`unexpected ${path}`);
};
vm.runInContext('api=mockApi',ctx);
await vm.runInContext('deckyChange("update",{id:2,name:"Plugin 2",sha256:"b".repeat(64)})',ctx);
assert.match(el('deckyJobStatus').textContent,/Error: archive digest mismatch/);
assert.equal(session.has('frameyPluginJob'),false);

// Polling can lose the connection after the server accepted a plugin job.
// Keep both store and installed controls disabled until its saved ID resolves.
let changes=0;
ctx.mockApi=async (path,body) => {
  if(path==='/api/decky/plugin'){changes++;return {job:'job-pending'};}
  if(path.startsWith('/api/job'))throw Error('connection lost');
  if(path==='/api/decky')return {managed:true,running:true,
    plugins:[{storeId:2,name:'Plugin 2',version:'1.0'}]};
  throw Error(`unexpected ${path}`);
};
vm.runInContext('api=mockApi',ctx);
await vm.runInContext('deckyChange("install",{id:2,name:"Plugin 2",sha256:"a".repeat(64)})',ctx);
assert.equal(changes,1);
assert.equal(session.has('frameyPluginJob'),true);
assert.equal(el('deckyJobCheck').hidden,false);
assert.equal(el('deckyInstalled').children[0].children.find(child=>child.textContent==='Open panel').disabled,true);
assert.equal(el('deckyInstalled').children[0].children.find(child=>child.textContent==='Remove').disabled,true);
assert.equal(el('deckyStoreList').children[1].children[1].disabled,true);
await vm.runInContext('deckyChange("remove",{id:2,name:"Plugin 2"})',ctx);
assert.equal(changes,1);
assert.match(el('deckyJobStatus').textContent,/Check result before starting another/);
ctx.mockApi=async path => {
  if(path.startsWith('/api/job'))return {done:true,message:'Installed Plugin 2'};
  if(path==='/api/decky')return {managed:true,running:true,
    plugins:[{storeId:2,name:'Plugin 2',version:'1.0'}]};
  throw Error(`unexpected ${path}`);
};
vm.runInContext('api=mockApi',ctx);
await vm.runInContext('checkDeckyJob()',ctx);
assert.equal(session.has('frameyPluginJob'),false);
assert.equal(el('deckyInstalled').children[0].children.find(child=>child.textContent==='Open panel').disabled,false);
assert.equal(el('deckyInstalled').children[0].children.find(child=>child.textContent==='Remove').disabled,false);
assert.equal(el('deckyStoreList').children[1].children[1].disabled,false);

// A failed refresh must remove old install buttons. A late older response
// must not replace the newer catalog the wearer just requested.
ctx.mockApi=async path => {assert.equal(path,'/api/decky/store');throw Error('offline');};
vm.runInContext('api=mockApi',ctx);
await vm.runInContext('loadDeckyStore()',ctx);
assert.match(el('deckyStoreSummary').textContent,/Store unavailable: offline/);
assert.equal(el('deckyStoreList').children.length,0);
let finishOld, finishNew;
ctx.mockApi=path => {assert.equal(path,'/api/decky/store');
  return new Promise(resolve=>{if(!finishOld)finishOld=resolve;else finishNew=resolve;});};
vm.runInContext('api=mockApi',ctx);
const old=vm.runInContext('loadDeckyStore()',ctx);
const current=vm.runInContext('loadDeckyStore()',ctx);
assert.equal(el('deckyStoreList').children.length,0);
assert.equal(el('deckyStoreSummary').textContent,'Loading official Decky store…');
finishNew({plugins:[{id:98,name:'Current',version:'2.0',description:'Latest'}]});
await current;
finishOld({plugins:[{id:97,name:'Stale',version:'1.0',description:'Older'}]});
await old;
assert.match(el('deckyStoreList').children[0].children[0].textContent,/Current/);
assert.doesNotMatch(el('deckyStoreList').children[0].children[0].textContent,/Stale/);

// A saved job does not survive a server restart. Clear it instead of offering
// Check result forever for an ID that the new server cannot know.
session.set('frameyPluginJob',JSON.stringify({job:'old-job',action:'install',name:'Plugin 2'}));
ctx.mockApi=async path => {
  if(path.startsWith('/api/job'))throw Error('no such job (the app may have restarted)');
  if(path==='/api/decky')return {running:true,plugins:[]};
  throw Error(`unexpected ${path}`);
};
vm.runInContext('api=mockApi',ctx);
await vm.runInContext('checkDeckyJob()',ctx);
assert.match(el('deckyJobStatus').textContent,/server has no record of this request/);
assert.equal(el('deckyJobCheck').hidden,true);
assert.equal(session.has('frameyPluginJob'),false);
assert.equal(el('deckyStoreList').children[0].children[1].disabled,false);

// Known hardware blockers remain visible, cannot install, and keep their reason in the opened panel.
ctx.hardware={id:900,name:'Hardware only',version:'1.0',description:'Fan control',root:false,
  compatibility:{status:'na',reason:'Not supported on Frame: Deck fan hardware.',verification:['static archive','local browser'],blockInstall:true}};
el('deckySearch').value='';el('deckyStoreFilter').value='all';
vm.runInContext('deckyStore=[hardware];deckyState={running:true,plugins:[{...hardware,storeId:900}]};showDeckyStore()',ctx);
const hardwareRow=el('deckyStoreList').children[0];
assert.equal(hardwareRow.children[1].disabled,true);
assert.match(hardwareRow.children[0].children[0].textContent,/N\/A: Not supported on Frame/);
el('deckyStoreFilter').value='compatible';vm.runInContext('showDeckyStore()',ctx);
assert.equal(el('deckyStoreList').children.length,0);
vm.runInContext('openFrameyPanel(900,"Hardware only")',ctx);
assert.match(el('frameyCompatibility').textContent,/Deck fan hardware/);
assert.match(el('frameyCompatibility').textContent,/local browser/);

// A failed installed-status read must not leave stale Remove or Install actions.
// Older responses must not replace a newer status, even if they arrive last.
vm.runInContext('deckyStore=[{id:2,name:"Plugin 2",version:"1.0",description:"A panel",root:false}];' +
  'deckyState={running:true,plugins:[{storeId:2,name:"Plugin 2",version:"1.0"}]};showDeckyStore()',ctx);
let statusCalls=[];
ctx.mockApi=path=>{assert.equal(path,'/api/decky');
  return new Promise((resolve,reject)=>statusCalls.push({resolve,reject}));};
vm.runInContext('api=mockApi',ctx);
const staleSuccess=vm.runInContext('refreshDecky()',ctx);
const latestFailure=vm.runInContext('refreshDecky()',ctx);
statusCalls[1].reject(Error('offline'));
await latestFailure;
assert.match(el('deckyState').textContent,/Installed plugins unavailable: offline/);
assert.equal(el('deckyInstalled').children.length,0);
assert.equal(el('deckyInstalled').textContent,'Refresh to check installed plugins.');
assert.equal(el('deckyStoreList').children[0].children[1].disabled,true);
statusCalls[0].resolve({running:true,plugins:[{storeId:2,name:'Stale',version:'1.0'}]});
await staleSuccess;
assert.match(el('deckyState').textContent,/offline/);
assert.equal(el('deckyInstalled').children.length,0);

statusCalls=[];
const staleFailure=vm.runInContext('refreshDecky()',ctx);
const latestSuccess=vm.runInContext('refreshDecky()',ctx);
statusCalls[1].resolve({managed:true,running:true,plugins:[{storeId:2,name:'Current',version:'1.0'}]});
await latestSuccess;
statusCalls[0].reject(Error('old offline error'));
await staleFailure;
assert.match(el('deckyInstalled').children[0].children[0].textContent,/Current/);
assert.doesNotMatch(el('deckyState').textContent,/offline/);
assert.equal(el('deckyStoreList').children[0].children[1].disabled,false);

// A panel must not keep an old frontend after the installed receipt changes.
let installedHash='a'.repeat(64);
ctx.mockApi=async path => {
  assert.equal(path,'/api/decky');
  return {managed:true,running:true,plugins:[{storeId:2,name:'Plugin 2',version:'1.0',sha256:installedHash}]};
};
vm.runInContext('api=mockApi',ctx);
await vm.runInContext('refreshDecky()',ctx);
vm.runInContext('openFrameyPanel(2,"Plugin 2")',ctx);
assert.equal(el('frameyPanel').hidden,false);
await vm.runInContext('refreshDecky()',ctx);
assert.equal(el('frameyPanel').hidden,false,'unchanged receipt keeps the current panel');
installedHash='b'.repeat(64);
await vm.runInContext('refreshDecky()',ctx);
assert.equal(el('frameyPanel').hidden,true);
assert.equal(el('frameyFrame').src,undefined);
assert.match(el('deckyState').textContent,/old plugin panel was closed/);

// The panel closes before updating its own backend, and stale Open handlers
// cannot recreate it while a job is active.
vm.runInContext('openFrameyPanel(2,"Plugin 2")',ctx);
assert.equal(el('frameyPanel').hidden,false);
ctx.mockApi=async (path,body) => {
  if(path==='/api/decky/plugin'){
    assert.equal(el('frameyPanel').hidden,true);
    vm.runInContext('openFrameyPanel(2,"Plugin 2")',ctx);
    assert.equal(el('frameyPanel').hidden,true);
    return {job:'job-update'};
  }
  if(path.startsWith('/api/job'))return {done:true,message:'Updated Plugin 2'};
  if(path==='/api/decky')return {managed:true,running:true,
    plugins:[{storeId:2,name:'Plugin 2',version:'2.0',sha256:'c'.repeat(64)}]};
  throw Error(`unexpected ${path}`);
};
vm.runInContext('api=mockApi',ctx);
await vm.runInContext('deckyChange("update",{id:2,name:"Plugin 2",sha256:"c".repeat(64)})',ctx);
assert.equal(el('frameyPanel').hidden,true);
assert.match(el('deckyJobStatus').textContent,/Old plugin panel closed; reopen it/);
vm.runInContext('openFrameyPanel(2,"Plugin 2")',ctx);
ctx.mockApi=async()=>{throw Error('offline');};
vm.runInContext('api=mockApi',ctx);
await vm.runInContext('refreshDecky()',ctx);
assert.equal(el('frameyPanel').hidden,true);
assert.match(el('deckyState').textContent,/panel was closed until status can be refreshed/);

// A denied sessionStorage must not lose an accepted job in the current panel.
// Keep Update/Remove disabled after a polling outage and allow Check result.
for(const method of ['getItem','setItem','removeItem'])
  ctx.sessionStorage[method]=()=>{throw Error('storage denied');};
let accepted=0;
ctx.mockApi=async path => {
  if(path==='/api/decky/plugin'){accepted++;return {job:'memory-job'};}
  if(path.startsWith('/api/job'))throw Error('connection lost');
  if(path==='/api/decky')return {managed:true,running:true,
    plugins:[{storeId:2,name:'Plugin 2',version:'1.0'}]};
  throw Error(`unexpected ${path}`);
};
vm.runInContext('api=mockApi;deckyState={managed:true,running:true,plugins:[]};' +
  'deckyStore=[{id:2,name:"Plugin 2",version:"1.0",description:"A panel",root:false}];showDeckyStore()',ctx);
await vm.runInContext('deckyChange("install",{id:2,name:"Plugin 2",sha256:"a".repeat(64)})',ctx);
assert.equal(accepted,1);
assert.equal(vm.runInContext('deckyJobPending()',ctx),true);
assert.equal(el('deckyJobCheck').hidden,false);
assert.equal(el('deckyInstalled').children[0].children.find(child=>child.textContent==='Remove').disabled,true);
await vm.runInContext('deckyChange("remove",{id:2,name:"Plugin 2"})',ctx);
assert.equal(accepted,1);
ctx.mockApi=async path => {
  if(path.startsWith('/api/job'))return {done:true,message:'Installed Plugin 2'};
  if(path==='/api/decky')return {managed:true,running:true,
    plugins:[{storeId:2,name:'Plugin 2',version:'1.0'}]};
  throw Error(`unexpected ${path}`);
};
vm.runInContext('api=mockApi',ctx);
await vm.runInContext('checkDeckyJob()',ctx);
assert.equal(vm.runInContext('deckyJobPending()',ctx),false);
assert.equal(el('deckyJobCheck').hidden,true);
assert.equal(el('deckyInstalled').children[0].children.find(child=>child.textContent==='Remove').disabled,false);

// Opening the headset panel with a key in its URL must survive denied storage.
const deniedDocument={getElementById:id=>new Element(id),createElement:()=>new Element()};
const deniedBoot=vm.createContext({document:deniedDocument,
  location:{hash:'#private-key',pathname:'/'},history:{replaceState(){}},
  sessionStorage:{getItem(){throw Error('storage denied');},setItem(){throw Error('storage denied');}},
  window:{addEventListener(){}},setInterval(){},setTimeout(){},confirm:()=>true,console,
  fetch(){throw Error('No network expected');}});
vm.runInContext(script,deniedBoot);
assert.equal(vm.runInContext('key',deniedBoot),'private-key');
