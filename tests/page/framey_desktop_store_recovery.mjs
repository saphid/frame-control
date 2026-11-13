// Real desktop store/job functions, synthetic replies and private session storage.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {webcrypto} from 'node:crypto';
import vm from 'node:vm';

const html=readFileSync(new URL('../../ui/index.html',import.meta.url),'utf8');
const start=html.indexOf('function deckyCompatibilityText(');
const store=html.slice(start,html.indexOf("$('deckyRefresh').onclick",start));
const jobStart=html.indexOf('async function runJob(');
const runJob=html.slice(jobStart,html.indexOf('// The install queue as the server has it:',jobStart));
const status={managed:true,running:true,arch:'aarch64',variant:'vr',cef:true,
  plugins:[{storeId:2,name:'Private fixture',version:'1',sha256:'a'.repeat(64)}],upstreamPlugins:[]};
const plugin={id:2,name:'Private fixture',version:'2',sha256:'b'.repeat(64),installedSha256:'a'.repeat(64)};
const tick=()=>new Promise(resolve=>setImmediate(resolve));
class Element {
  constructor(tag='div'){Object.assign(this,{tag,children:[],textContent:'',checked:true,value:'',disabled:false,hidden:false});}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=nodes;this.textContent='';}
  querySelectorAll(tag){return this.children.flatMap(node=>[
    ...(node.tag===tag?[node]:[]),...node.querySelectorAll(tag)]);}
}
function fixture(storage=new Map(),denied=false) {
  const elements=new Map(),requests=[],posts=[],confirms=[];
  const $=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
  const access=()=>{if(denied)throw Error('Synthetic storage denied');};
  const ctx=vm.createContext({$,document:{createElement:tag=>new Element(tag)},crypto:webcrypto,
    window:{connDevice:'private-frame'},sessionStorage:{
      getItem:key=>{access();return storage.get(key)||null;},
      setItem:(key,value)=>{access();storage.set(key,String(value));},
      removeItem:key=>{access();storage.delete(key);}},
    api:(path,body,device)=>{
      if(body)posts.push({path,body,device});
      return new Promise((resolve,reject)=>requests.push({path,resolve,reject}));},
    confirm:message=>{confirms.push(message);return true;},
    setTimeout:callback=>setImmediate(callback),
    installing:new Set(),queued:new Set(),jobsRunning:0,showJobs(){},log(){},toast(){},loadQueue(){}});
  vm.runInContext(store+runJob,ctx);
  const call=expression=>vm.runInContext(expression,ctx);
  const take=path=>{const index=requests.findIndex(r=>r.path===path);assert.ok(index>=0,'missing '+path);return requests.splice(index,1)[0];};
  const next=async path=>{
    for(let n=0;n<5&&!requests.some(r=>r.path===path);n++)await tick();
    return take(path);
  };
  const refresh=async(review=false,data=status)=>{const read=call(`loadDecky(${review})`);take('/api/decky').resolve(data);await read;};
  const change=()=>{ctx.plugin=plugin;return call('changeDeckyPlugin("update",plugin)');};
  const buttons=()=>[...$('deckyStoreList').querySelectorAll('button'),...$('deckyManagedList').querySelectorAll('button')];
  const assertLocked=()=>assert.ok(buttons().length&&buttons().every(b=>b.disabled),'unknown job unlocked plugin actions');
  const setup=async()=>{await refresh();ctx.plugin=plugin;call('deckyCatalog=[plugin];showDeckyStore()');};
  const endRefresh=async pending=>{(await next('/api/decky')).resolve(status);await pending;};
  return {storage,$,ctx,requests,posts,confirms,call,take,next,refresh,change,buttons,assertLocked,setup,endRefresh};
}

// A lost POST response must retain the pre-reserved ID, without another POST.
const f=fixture();await f.setup();let pending=f.change();
assert.equal(f.posts.length,1);
const id=f.posts[0].body.requestId;
assert.match(id||'',/^[0-9a-f]{32}$/,'desktop POST must reserve a recoverable job ID');
assert.equal(f.posts[0].device,'private-frame');
f.take('/api/decky/plugin').reject(Error('Synthetic lost POST reply'));await f.endRefresh(pending);
f.assertLocked();assert.equal(f.$('deckyPluginJobCheck').hidden,false);
await f.refresh();f.$('deckyAck').checked=false;f.$('deckyAck').onchange();
f.$('deckyAck').checked=true;f.$('deckyAck').onchange();f.assertLocked();
await f.change();assert.equal(f.posts.length,1);assert.equal(f.confirms.length,1);

// Restoring the same tab/session after a page reload restores the gate and ID.
const restored=fixture(f.storage);await restored.setup();restored.assertLocked();
await restored.change();assert.equal(restored.posts.length,0);
pending=restored.call('checkDesktopDeckyJob()');await tick();
(await restored.next('/api/job?id='+id)).resolve({done:true,queued:false,result:{},message:'Synthetic recovered'});
await tick();await tick();restored.assertLocked();
restored.take('/api/decky').resolve(status);await pending;
assert.equal(restored.posts.length,0,'Check result must never resubmit the plugin change');
assert.ok(restored.buttons().every(b=>!b.disabled));
assert.equal(restored.$('deckyPluginJobCheck').hidden,true);
assert.equal(restored.call('jobsRunning'),0);

// Accepted jobs survive exhausted polling failures and can be checked again.
pending=restored.change();const second=restored.posts[0].body.requestId;
restored.take('/api/decky/plugin').resolve({job:second});
for(let n=0;n<20;n++) (await restored.next('/api/job?id='+second)).reject(Error('Synthetic poll failure'));
await restored.endRefresh(pending);restored.assertLocked();
pending=restored.call('checkDesktopDeckyJob()');await tick();
(await restored.next('/api/job?id='+second)).resolve({done:true,queued:false,error:'Synthetic terminal failure'});
await restored.endRefresh(pending);
assert.ok(restored.buttons().every(b=>!b.disabled),'known terminal failure should release after status refresh');
assert.match(restored.$('deckyPluginJobState').textContent,/Synthetic terminal failure/);
assert.equal(restored.posts.length,1);

// Missing server records remain uncertain until a successful explicit review.
pending=restored.change();const missing=restored.posts.at(-1).body.requestId;
restored.take('/api/decky/plugin').reject(Error('Synthetic lost request'));await restored.endRefresh(pending);
pending=restored.call('checkDesktopDeckyJob()');await tick();
(await restored.next('/api/job?id='+missing)).reject(Error('no such job (the app may have restarted)'));
await restored.endRefresh(pending);restored.assertLocked();
assert.equal(restored.$('deckyPluginJobCheck').hidden,true);
const missingReload=fixture(restored.storage);await missingReload.setup();missingReload.assertLocked();
assert.equal(missingReload.$('deckyPluginJobCheck').hidden,true,'missing-result review gate did not survive reload');
await restored.refresh();restored.assertLocked();
let review=restored.call('loadDecky(true)');restored.take('/api/decky').reject(Error('Synthetic offline'));await review;
await restored.refresh();restored.assertLocked();
review=restored.call('loadDecky(true)');restored.take('/api/decky').resolve({managed:true,running:true});await review;
await restored.refresh();restored.assertLocked();
await restored.refresh(true);assert.ok(restored.buttons().every(b=>!b.disabled));

// A malformed successful POST cannot turn into a poll of an unrelated job.
pending=restored.change();restored.take('/api/decky/plugin').resolve({job:'unrelated'});
await restored.endRefresh(pending);restored.assertLocked();
assert.equal(restored.requests.length,0);

// A retained request is bound to the headset it originally targeted.
restored.ctx.window.connDevice='another-private-frame';
const reads=restored.requests.length;await restored.call('checkDesktopDeckyJob()');
assert.equal(restored.requests.length,reads);await restored.change();assert.equal(restored.posts.length,3);
await restored.refresh(true);restored.assertLocked();
assert.match(restored.$('deckyPluginJobState').textContent,/original headset/i);

// Denied session storage still supports recovery within this open page.
const denied=fixture(new Map(),true);await denied.setup();pending=denied.change();
const deniedId=denied.posts[0].body.requestId;
denied.take('/api/decky/plugin').reject(Error('Synthetic lost reply'));await denied.endRefresh(pending);denied.assertLocked();
pending=denied.call('checkDesktopDeckyJob()');await tick();
(await denied.next('/api/job?id='+deniedId)).resolve({done:true,queued:false,result:{},message:'Recovered in memory'});
await denied.endRefresh(pending);assert.ok(denied.buttons().every(b=>!b.disabled));assert.equal(denied.posts.length,1);

// A definite pre-acceptance HTTP rejection does not leave a phantom request.
pending=denied.change();denied.take('/api/decky/plugin').reject(Object.assign(Error('Synthetic reviewed receipt changed'),{status:409}));
await denied.endRefresh(pending);assert.ok(denied.buttons().every(b=>!b.disabled));
assert.equal(denied.$('deckyPluginJobCheck').hidden,true);
assert.equal(denied.call('jobsRunning'),0);

// Switching headsets during a poll cannot accept the old target's completion.
pending=denied.change();const switchingId=denied.posts.at(-1).body.requestId;
denied.take('/api/decky/plugin').resolve({job:switchingId});
const polling=await denied.next('/api/job?id='+switchingId);
denied.ctx.window.connDevice='another-private-frame';polling.resolve({done:true,queued:false,result:{}});
await denied.endRefresh(pending);denied.assertLocked();
assert.equal(denied.$('deckyPluginJobCheck').disabled,true);
denied.ctx.window.connDevice='private-frame';pending=denied.call('checkDesktopDeckyJob()');
(await denied.next('/api/job?id='+switchingId)).resolve({done:true,queued:false,result:{}});
await denied.endRefresh(pending);assert.ok(denied.buttons().every(b=>!b.disabled));
console.log('desktop store request recovery passed; synthetic API only, no headset contact');
