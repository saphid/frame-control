// Desktop store requests use synthetic replies only; no backend or Frame action.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const html=readFileSync(new URL('../../ui/index.html',import.meta.url),'utf8');
const start=html.indexOf('function deckyCompatibilityText(');
const end=html.indexOf("$('deckyAck').onchange",start);
assert.ok(start>0&&end>start);
class Element {
  constructor(){this.children=[];this.textContent='';this.checked=true;this.value='';this.disabled=false;}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=nodes;this.textContent='';}
}
const elements=new Map();
const $=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
const requests=[];let posts=0,confirms=0;
const ctx=vm.createContext({$,document:{createElement:()=>new Element()},
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
  if(path==='/api/decky/plugin'){mutation=body;return Promise.resolve({job:'synthetic-remove'});}
  return read(path);
};
ctx.runJob=async(_title,_kind,send)=>{posts++;await send();};
const removing=removeStopped.onclick();
await new Promise(resolve=>setImmediate(resolve));
requests.shift().resolve(stopped);await removing;
assert.equal(mutation.action,'remove');assert.equal(mutation.id,2);
assert.equal(posts,1);assert.equal(confirms,beforeBlocked+1);
