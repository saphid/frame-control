// Desktop store requests use synthetic replies only; no backend or Frame action.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {webcrypto} from 'node:crypto';

const html=readFileSync(new URL('../../ui/index.html',import.meta.url),'utf8');
const start=html.indexOf('function deckyCompatibilityText(');
const end=html.indexOf("$('deckyRefresh').onclick",start);
assert.ok(start>0&&end>start);
class Element {
  constructor(tag='div'){this.tag=tag;this.children=[];this.textContent='';this.checked=true;this.value='';this.disabled=false;}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=nodes;this.textContent='';}
  querySelectorAll(tag){return this.children.flatMap(node=>[
    ...(node.tag===tag?[node]:[]),...node.querySelectorAll(tag)]);}
}
const elements=new Map();
const $=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
const requests=[];let posts=0,confirms=0;
const ctx=vm.createContext({$,document:{createElement:tag=>new Element(tag)},crypto:webcrypto,
  api:path=>{assert.ok(['/api/decky','/api/decky/store'].includes(path));
    return new Promise((resolve,reject)=>requests.push({path,resolve,reject}));},
  confirm:()=>{confirms++;return true;},runJob:()=>{posts++;throw Error('No mutation expected');}});
vm.runInContext(html.slice(start,end),ctx);
const plugin={id:2,name:'Private fixture',description:'A panel',version:'1',sha256:'a'.repeat(64),root:false};
const state=name=>({managed:true,running:true,arch:'aarch64',variant:'vr',cef:true,
  plugins:[{storeId:2,name,version:'1',sha256:'a'.repeat(64)}],upstreamPlugins:[]});
ctx.plugin=plugin;
function call(expression){return vm.runInContext(expression,ctx);}
async function installStatus(name='Current'){
  const promise=call('loadDecky()');requests.shift().resolve(state(name));await promise;
}
await installStatus();
call('deckyCatalog=[plugin];showDeckyStore()');
assert.equal($('deckyManagedList').children.length,1);
const oldRemove=$('deckyManagedList').children[0].children[1];
const oldInstall=$('deckyStoreList').children[0].children.find(node=>node.textContent==='Reinstall');
const offline=call('loadDecky()');
await oldRemove.onclick();await oldInstall.onclick();
assert.equal(posts,0,'actions must wait for the requested status refresh');
assert.equal(confirms,0);
requests.shift().reject(Error('offline'));await offline;
assert.equal($('deckyManagedList').children.length,0,'failed status must remove old Remove actions');
assert.match($('deckyManagedList').textContent,/Refresh/);
assert.doesNotMatch($('deckyPlugins').textContent,/Current/,'failed status must not describe an old list as installed');
assert.equal($('deckyStoreList').children[0].children.find(node=>node.textContent==='Install').disabled,true);
await oldRemove.onclick();await oldInstall.onclick();
assert.equal(posts,0,'retained old actions must not post when installed status is unavailable');
assert.equal(confirms,0,'invalidated actions must stop before asking for confirmation');

// A later failure beats an older success. Then a later success beats an old failure.
let older=call('loadDecky()'),newer=call('loadDecky()');
const olderRequest=requests.shift(),newerRequest=requests.shift();
newerRequest.reject(Error('latest offline'));await newer;
olderRequest.resolve(state('Stale'));await older;
assert.match($('deckyState').textContent,/latest offline/);
assert.equal($('deckyManagedList').children.length,0);
older=call('loadDecky()');newer=call('loadDecky()');
const oldFailure=requests.shift(),newSuccess=requests.shift();
newSuccess.resolve(state('Newest'));await newer;
oldFailure.reject(Error('obsolete offline'));await older;
assert.match($('deckyManagedList').children[0].children[0].textContent,/Newest/);
assert.doesNotMatch($('deckyState').textContent,/offline/);
assert.equal($('deckyStoreList').children[0].children.find(node=>node.textContent==='Reinstall').disabled,false);

// Catalog refresh invalidates old rows immediately, and failed refreshes keep them gone.
const failingCatalog=call('loadDeckyStore()');
assert.equal($('deckyStoreList').children.length,0,'old catalog choices disappear during refresh');
requests.shift().reject(Error('catalog offline'));await failingCatalog;
assert.equal($('deckyStoreList').children.length,0);
assert.match($('deckyStoreState').textContent,/catalog offline/);
older=call('loadDeckyStore()');newer=call('loadDeckyStore()');
const oldCatalog=requests.shift(),newCatalog=requests.shift();
newCatalog.resolve({plugins:[{...plugin,name:'New catalog',version:'2'}]});await newer;
oldCatalog.resolve({plugins:[{...plugin,name:'Stale catalog'}]});await older;
assert.match($('deckyStoreList').children[0].children[0].textContent,/New catalog/);
assert.doesNotMatch($('deckyStoreList').children[0].children[0].textContent,/Stale/);
older=call('loadDeckyStore()');newer=call('loadDeckyStore()');
const obsoleteCatalog=requests.shift(),freshCatalog=requests.shift();
freshCatalog.resolve({plugins:[{...plugin,name:'Newest catalog',version:'3'}]});await newer;
obsoleteCatalog.reject(Error('obsolete catalog error'));await older;
assert.match($('deckyStoreList').children[0].children[0].textContent,/Newest catalog/);
assert.doesNotMatch($('deckyStoreState').textContent,/obsolete/);
assert.equal(posts,0);

// Recovery removal remains available with a fresh managed-but-stopped status.
const stopped={...state('Stopped plugin'),running:false};
const stoppedRead=call('loadDecky()');requests.shift().resolve(stopped);await stoppedRead;
const removeStopped=$('deckyManagedList').children[0].children[1];
assert.equal(removeStopped.disabled,false);
const beforeBlocked=confirms;
await call('changeDeckyPlugin("update",plugin)');
assert.equal(posts,0);assert.equal(confirms,beforeBlocked);
let mutation;
const read=ctx.api;
ctx.api=(path,body)=>{
  if(path==='/api/decky/plugin'){mutation=body;return Promise.resolve({job:body.requestId});}
  return read(path);
};
ctx.runJob=async(_title,_kind,send,progress)=>{posts++;await send();progress({done:true});};
const removing=removeStopped.onclick();
await new Promise(resolve=>setImmediate(resolve));
requests.shift().resolve(stopped);await removing;
assert.equal(mutation.action,'remove');assert.equal(mutation.id,2);
assert.equal(posts,1);assert.equal(confirms,beforeBlocked+1);

// A second store action must not create another job before the first settles,
// even when React/DOM redraw, acknowledgement changes or refreshes intervene.
await installStatus();
call('deckyCatalog=[plugin];showDeckyStore()');
const buttons=()=>$('deckyStoreList').querySelectorAll('button');
const retainedUpdate=buttons().find(node=>node.textContent==='Reinstall').onclick;
const retainedRemove=$('deckyManagedList').querySelectorAll('button')[0].onclick;
const jobs=[];
ctx.runJob=(_title,_kind,send,progress)=>{posts++;return new Promise((resolve,reject)=>jobs.push({
  resolve:value=>{progress({done:true});resolve(value);},
  reject:error=>{progress({done:true,error:error.message});reject(error);},send}));};
const beforeJobPosts=posts,beforeJobConfirms=confirms;
const firstChange=retainedUpdate();
const duplicateUpdate=retainedUpdate(),duplicateRemove=retainedRemove();
assert.equal(posts,beforeJobPosts+1,'retained callbacks must not start overlapping plugin jobs');
await duplicateUpdate;await duplicateRemove;
assert.equal(confirms,beforeJobConfirms+1,'busy callbacks must stop before confirmation');
assert.ok(buttons().every(node=>node.disabled),'store plugin buttons stay disabled during a job');
assert.ok($('deckyManagedList').querySelectorAll('button').every(node=>node.disabled),'installed Remove stays disabled');
$('deckyAck').checked=false;$('deckyAck').onchange();
$('deckyAck').checked=true;$('deckyAck').onchange();
assert.ok(buttons().every(node=>node.disabled),'acknowledgement cannot unlock a running job');
assert.ok($('deckyManagedList').querySelectorAll('button').every(node=>node.disabled));
await installStatus();
assert.ok(buttons().every(node=>node.disabled),'manual refresh cannot unlock a running job');
assert.ok($('deckyManagedList').querySelectorAll('button').every(node=>node.disabled));
await retainedRemove();assert.equal(posts,beforeJobPosts+1);
jobs.shift().resolve({});
await new Promise(resolve=>setImmediate(resolve));
assert.equal(requests.length,1,'job completion must refresh installed status');
await retainedUpdate();await retainedRemove();
assert.equal(posts,beforeJobPosts+1,'job lock must extend through the final status read');
requests.shift().resolve(state('After job'));await firstChange;
assert.ok(buttons().every(node=>!node.disabled),'successful job and refresh restore store actions');
assert.ok($('deckyManagedList').querySelectorAll('button').every(node=>!node.disabled));

// Failures release the local busy guard so an explicit retry is possible.
const failedChange=retainedUpdate();jobs.shift().reject(Error('job fixture failed'));
await new Promise(resolve=>setImmediate(resolve));requests.shift().resolve(state('After terminal error'));await failedChange;
assert.match($('deckyPluginJobState').textContent,/job fixture failed/);
const afterFailure=retainedRemove();assert.equal(jobs.length,1,'failed job must release the guard');
jobs.shift().resolve({});await new Promise(resolve=>setImmediate(resolve));
requests.shift().reject(Error('status fixture failed'));await afterFailure;
assert.ok(buttons().every(node=>node.disabled),'failed final status must keep changes unavailable');
const afterFailedRead=posts;await retainedUpdate();await retainedRemove();
assert.equal(posts,afterFailedRead,'a released job lock cannot bypass unavailable installed status');
await installStatus();
const retry=retainedUpdate();assert.equal(jobs.length,1,'fresh status must permit a new explicit job');
jobs.shift().resolve({});await new Promise(resolve=>setImmediate(resolve));
requests.shift().resolve(state('Retried'));await retry;

// Every catalogue entry must be reachable, including rows beyond the first 40.
// Browsing and search must never submit a job or erase a catalogue/job error.
const beforeBrowsingPosts=posts;
const catalog=Array.from({length:93},(_,index)=>({...plugin,id:index+1,
  name:`Fixture ${index+1}`,author:index===84?'Distinct author':'Maker'}));
const catalogRead=call('loadDeckyStore()');requests.shift().resolve({plugins:catalog});await catalogRead;
assert.equal($('deckyStoreList').children.length,40);
assert.match($('deckyStorePage').textContent,/Page 1 of 3/);
assert.equal($('deckyStorePrevious').disabled,true);
$('deckyStoreNext').onclick();
assert.match($('deckyStoreList').children[0].children[0].textContent,/Fixture 41 ·/);
assert.match($('deckyStorePage').textContent,/Page 2 of 3/);
await installStatus();
assert.match($('deckyStorePage').textContent,/Page 2 of 3/,'status refresh must retain the page');
$('deckyStoreNext').onclick();
assert.equal($('deckyStoreList').children.length,13);
assert.match($('deckyStoreList').children[12].children[0].textContent,/Fixture 93 ·/);
assert.equal($('deckyStoreNext').disabled,true);
$('deckyStoreNext').onclick();
assert.match($('deckyStorePage').textContent,/Page 3 of 3/,'retained callback cannot pass the last page');
$('deckyStorePrevious').onclick();assert.match($('deckyStorePage').textContent,/Page 2 of 3/);
$('deckyStoreSearch').value='distinct AUTHOR';$('deckyStoreSearch').oninput();
assert.equal($('deckyStoreList').children.length,1);
assert.match($('deckyStoreList').children[0].children[0].textContent,/Fixture 85 ·/);
assert.match($('deckyStorePage').textContent,/Page 1 of 1/);
assert.equal($('deckyStorePrevious').disabled,true);assert.equal($('deckyStoreNext').disabled,true);
$('deckyStoreSearch').value='no matching fixture';$('deckyStoreSearch').oninput();
assert.equal($('deckyStoreList').children.length,0);
assert.match($('deckyStorePage').textContent,/0 plugins found/);
$('deckyStoreSearch').value='';$('deckyStoreSearch').oninput();
assert.match($('deckyStorePage').textContent,/Page 1 of 3/);
$('deckyStorePrevious').onclick();assert.match($('deckyStorePage').textContent,/Page 1 of 3/);
$('deckyStoreNext').onclick();$('deckyStoreNext').onclick();
const smallerRead=call('loadDeckyStore()');
assert.equal($('deckyStoreList').children.length,0);
assert.equal($('deckyStorePage').textContent,'','loading must not describe an empty catalogue as results');
assert.equal($('deckyStorePrevious').disabled,true);assert.equal($('deckyStoreNext').disabled,true);
requests.shift().resolve({plugins:catalog.slice(0,3)});await smallerRead;
assert.equal($('deckyStoreList').children.length,3);assert.match($('deckyStorePage').textContent,/Page 1 of 1/);
const unavailable=call('loadDeckyStore()');requests.shift().reject(Error('catalogue unavailable'));await unavailable;
$('deckyStoreSearch').value='Fixture';$('deckyStoreSearch').oninput();
$('deckyStoreNext').onclick();$('deckyStorePrevious').onclick();await installStatus();
assert.equal($('deckyStoreState').textContent,'catalogue unavailable');
assert.equal($('deckyStorePage').textContent,'');assert.equal($('deckyStoreList').children.length,0);
assert.equal($('deckyStorePrevious').disabled,true);assert.equal($('deckyStoreNext').disabled,true);
assert.equal(posts,beforeBrowsingPosts,'navigation/search/status reads must not submit plugin jobs');

// Stale row callbacks retain the receipt that was displayed.
{
const source=html.slice(html.indexOf('function deckyCompatibilityText('),html.indexOf('function deckyButtons()'));
class Element {
  constructor(){this.children=[];this.checked=true;this.value='';}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=nodes;}
}
const elements=new Map(),bodies=[];
const el=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
const context=vm.createContext({$:el,document:{createElement:()=>new Element()},confirm:()=>true,crypto:webcrypto,
  deckyButtons(){},runJob:async (_name,_kind,submit,_progress,onError)=>{try{await submit();}catch(error){onError(error);}},
  api:async (path,body)=>{
    if(path==='/api/decky')return {managed:true,running:true,plugins:[
      {storeId:2,name:'Plugin',version:'1',sha256:'a'.repeat(64)}],upstreamPlugins:[]};
    if(path==='/api/decky/plugin'){bodies.push(body);throw Object.assign(Error('Installed plugin changed'),{status:409});}
    throw Error(`unexpected ${path}`);
  }});
vm.runInContext(source,context);
await vm.runInContext('loadDecky()',context);
vm.runInContext('deckyCatalog=[{id:2,name:"Plugin",version:"2",sha256:"d".repeat(64)}];showDeckyStore()',context);
const removeInstalled=el('deckyManagedList').children[0].children.find(c=>c.textContent==='Remove plugin').onclick;
const row=el('deckyStoreList').children[0];
const update=row.children.find(c=>c.textContent==='Update').onclick;
const removeStore=row.children.find(c=>c.textContent==='Remove').onclick;
vm.runInContext('deckyInfo.plugins[0]={...deckyInfo.plugins[0],sha256:"b".repeat(64)}',context);
for(const tap of [removeInstalled,update,removeStore])await tap();
assert.deepEqual(bodies.map(b=>b.action),['remove','update','remove']);
for(const body of bodies)assert.equal(body.installedSha256,'a'.repeat(64));
assert.equal(bodies[1].sha256,'d'.repeat(64),'reviewed store archive stays separate from installed receipt');
assert.equal(bodies[0].sha256,undefined);
assert.equal(bodies[2].sha256,undefined);
assert.match(el('deckyPluginJobState').textContent,/Installed plugin changed/);

vm.runInContext('deckyInfo.plugins=[];showDeckyStore()',context);
await el('deckyStoreList').children[0].children.find(c=>c.textContent==='Install').onclick();
assert.equal(bodies.at(-1).action,'install');
assert.equal(bodies.at(-1).installedSha256,undefined);
}
