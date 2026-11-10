import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const html=readFileSync(new URL('../../ui/headset.html',import.meta.url),'utf8');
const parentSource=html.match(/<script>([\s\S]*?)<\/script>/)[1].split('refresh();refreshGames();')[0];
const hostSource=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8')
  .replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n  window.__waitForSeed = waitForSeed; window.__start = start;\n})();');
assert.match(hostSource,/framey:cache:init/);
const values=new Map();
const localStorage={getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value)};
const elements=new Map();
const el=id=>{if(!elements.has(id))elements.set(id,{id,hidden:false,removeAttribute(){},scrollIntoView(){}});
  return elements.get(id);};
const parentListeners=[];
const parent=vm.createContext({document:{getElementById:el,createElement:()=>({})},
  location:{hash:'',pathname:'/'},history:{replaceState(){}},
  sessionStorage:{getItem:()=>null,setItem(){}},localStorage,
  window:{addEventListener:(type,fn)=>parentListeners.push({type,fn})},
  setTimeout(){},setInterval(){},fetch(){throw Error('No network expected');},console});
vm.runInContext(parentSource,parent);
vm.runInContext('deckyState={running:true,plugins:[{storeId:14,sha256:"a",version:"1"}]};openFrameyPanel(14,"Steam Status")',parent);
let session=vm.runInContext('frameySession',parent);
const firstURL=new URL(el('frameyFrame').src,'http://127.0.0.1');
const onParent=parentListeners.find(x=>x.type==='message').fn;

function iframe({delaySeed=false}={}){
  const listeners=[];const queued=[];const timers=[];let live=false,bundleReads=0;
  const frameWindow={location:{hash:`#${session}`},React:{Fragment:'fragment',Component:class {},forwardRef:render=>render,createElement:()=>({}),isValidElement:()=>true},
    ReactDOM:{createRoot:()=>({render(){}})}};
  const proxy={postMessage:message=>listeners.find(x=>x.type==='message')?.fn({source:hostParent,data:message})};
  el('frameyFrame').contentWindow=proxy;
  const hostParent={postMessage:message=>live?onParent({source:proxy,data:message}):queued.push(message)};
  const context=vm.createContext({window:frameWindow,document:{getElementById:id=>{if(id==='framey-bundle')bundleReads++;return {};}},
    navigator:{language:'en'},parent:hostParent,DOMException,
    addEventListener:(type,fn)=>listeners.push({type,fn}),
    setTimeout:(callback,ms)=>{timers.push({callback,ms,active:true});return timers.length;},
    clearTimeout:id=>{if(timers[id-1])timers[id-1].active=false;}});
  vm.runInContext(hostSource,context);
  context.localStorage=frameWindow.localStorage;
  live=true;
  const flushSeed=()=>{for(const message of queued)onParent({source:proxy,data:message});queued.length=0;};
  if(!delaySeed)flushSeed();
  const send=message=>onParent({source:proxy,data:message});
  return {storage:frameWindow.localStorage,steamStorage:frameWindow.SteamClient.Storage,
    evaluate:source=>vm.runInContext(source,context),
    waitForSeed:frameWindow.__waitForSeed,start:frameWindow.__start,get bundleReads(){return bundleReads;},timers,flushSeed,send,receive:message=>
      listeners.find(x=>x.type==='message').fn({source:hostParent,data:message})};
}
// Replay only the pinned Game Sync 1.0.4 cache functions, never its initializer,
// sync engine, backend calls or cloud operations. Python verifies the ZIP digest.
const official=readFileSync(process.argv[2],'utf8');
const start=official.indexOf('function autoSync() {');
const end=official.indexOf('\nclass SyncFilters ',start);
assert.ok(start>=0 && end>start,'published cache functions must still be identifiable');
const functions=official.slice(start,end);
assert.match(functions,/getKey\(appId\) in localStorage/);
const pathDeclaration=official.match(/^const PLUGIN_NAME_AS_PATH = .+;$/m)?.[0];
const globalDeclaration=official.match(/^const GLOBAL_SYNC_APP_ID = 0;$/m)?.[0];
assert.ok(pathDeclaration && globalDeclaration);
const replay=frame=>frame.evaluate(`
  const Plugin={name:'Game Sync'};
  const config=new Map([['sync_on_game_start',true],['sync_on_game_stop',true]]);
  ${pathDeclaration}\n${globalDeclaration}\n${functions}
  ({getKey,setInSync,getInSync,config})`);
const openPlugin=id=>{
  vm.runInContext(`deckyState={running:true,plugins:[{storeId:${id},sha256:'a',version:'1'}]};
    openFrameyPanel(${id},'Private cache fixture')`,parent);
  session=vm.runInContext('frameySession',parent);
  return iframe();
};
const appId=424242;
const gameSync=openPlugin(104), sync=replay(gameSync);
const marker=sync.getKey(appId);
assert.equal(sync.getInSync(appId),true);
sync.setInSync(appId,false);
assert.equal(gameSync.storage.getItem(marker),'');
assert.equal(sync.getInSync(appId),false,'a saved empty-string marker means out of sync');
assert.equal(marker in gameSync.storage,true);
assert.equal('not-a-saved-key' in gameSync.storage,false);
assert.equal('getItem' in gameSync.storage,true,'storage feature detection remains available');
assert.equal('length' in gameSync.storage,true);
assert.equal(Symbol('private') in gameSync.storage,false);
sync.config.set('sync_on_game_stop',false);
assert.equal(sync.getInSync(appId),true,'retain the official automatic-sync condition');
sync.config.set('sync_on_game_stop',true);
sync.setInSync(0,false);
assert.equal(sync.getInSync(0),true,'the global sync entry is not a per-game marker');
assert.equal(gameSync.storage.getItem(sync.getKey(0)),null);
const savedGameCache=values.get('framey-plugin-cache-v1:104');
assert.equal(JSON.parse(savedGameCache)[marker],'');
const afterReopen=openPlugin(104), reopenedSync=replay(afterReopen);
assert.equal(reopenedSync.getInSync(appId),false,'the same published callback must see the marker after reopen');
reopenedSync.setInSync(appId,true);
assert.equal(marker in afterReopen.storage,false);
assert.equal(reopenedSync.getInSync(appId),true);
reopenedSync.setInSync(appId,false);
afterReopen.storage.clear();
assert.equal(reopenedSync.getInSync(appId),true);
reopenedSync.setInSync(appId,false);
const otherPlugin=openPlugin(14);
assert.equal(marker in otherPlugin.storage,false,'membership must stay inside this plugin cache');
assert.equal(values.get('framey-plugin-cache-v1:104'),savedGameCache);

// Native Storage accepts direct string properties as well as setItem/getItem.
// Exercise the real parent snapshot and a fresh iframe, not only this wrapper.
otherPlugin.storage.preference='on';
assert.equal(otherPlugin.storage.getItem('preference'),'on','property assignment must enter the persisted cache');
otherPlugin.storage['empty-value']='';
otherPlugin.storage.count=0;
assert.equal(otherPlugin.storage.preference,'on');
assert.equal(otherPlugin.storage['empty-value'],'');
assert.equal(otherPlugin.storage.count,'0','property values use Storage string conversion');
assert.equal(otherPlugin.storage.absent,undefined);
assert.equal(otherPlugin.storage.getItem('absent'),null);
assert.equal(otherPlugin.storage.length,3);
let propertyReopen=openPlugin(14);
assert.equal(propertyReopen.storage.preference,'on','property save must survive a new host document');
assert.equal(propertyReopen.storage['empty-value'],'');
assert.equal(propertyReopen.storage.count,'0');
propertyReopen.storage.setItem('preference','off');
assert.equal(propertyReopen.storage.preference,'off','method writes must update property reads');
delete propertyReopen.storage.preference;
assert.equal(propertyReopen.storage.getItem('preference'),null);
assert.equal('preference' in propertyReopen.storage,false);
propertyReopen=openPlugin(14);
assert.equal(propertyReopen.storage.preference,undefined,'property deletion must survive reopen');
assert.equal(propertyReopen.storage.length,2);
const propertySnapshot=values.get('framey-plugin-cache-v1:14');
assert.throws(()=>{propertyReopen.storage.huge='x'.repeat(65537);},/Framey plugin cache is full/);
assert.equal(propertyReopen.storage.huge,undefined);
assert.equal(values.get('framey-plugin-cache-v1:14'),propertySnapshot,'rejected property write must preserve saved bytes');
// Reserved API/prototype names never replace the methods or prototype. Their
// stored strings remain reachable with getItem, just as for method writes.
propertyReopen.storage.getItem='reserved';
assert.equal(typeof propertyReopen.storage.getItem,'function');
assert.equal(propertyReopen.storage.getItem('getItem'),'reserved');
propertyReopen.storage.__proto__='saved prototype name';
assert.equal(typeof propertyReopen.storage.__proto__,'object');
assert.equal(propertyReopen.storage.getItem('__proto__'),'saved prototype name');
delete propertyReopen.storage.getItem;
assert.equal(typeof propertyReopen.storage.getItem,'function');
assert.equal(propertyReopen.storage.getItem('getItem'),null);
const isolatedProperties=openPlugin(104);
assert.equal(isolatedProperties.storage.count,undefined,'property values remain plugin-scoped');
assert.equal(values.get('framey-plugin-cache-v1:104'),savedGameCache);
propertyReopen=openPlugin(14);
propertyReopen.storage.clear();
assert.equal(propertyReopen.storage.count,undefined,'clear must retire property values too');
assert.equal(propertyReopen.storage.length,0);

let first=iframe();
assert.equal(first.storage.getItem('status-cache'),null);
first.storage.setItem('status-cache','{"online":true}');
assert.equal(values.get('framey-plugin-cache-v1:14'),'{"status-cache":"{\\"online\\":true}"}');
first.storage.setItem('temporary','discard');
first.storage.removeItem('temporary');
await first.steamStorage.SetObject('playtime-settings',{count:3});
const oldSession=session;
vm.runInContext('openFrameyPanel(14,"Steam Status")',parent);
session=vm.runInContext('frameySession',parent);
assert.notEqual(session,oldSession);
const reopenedURL=new URL(el('frameyFrame').src,'http://127.0.0.1');
// Fragment-only navigation preserves the old document, host and cache session.
assert.notEqual(reopenedURL.pathname+reopenedURL.search,firstURL.pathname+firstURL.search);
assert.equal(reopenedURL.searchParams.get('session'),session);
assert.equal(reopenedURL.hash.slice(1),session);
let reopened=iframe();
assert.equal(reopened.storage.getItem('status-cache'),'{"online":true}');
assert.equal(reopened.storage.length,2);
assert.equal(reopened.storage.key(0),'status-cache');
assert.equal(await reopened.steamStorage.GetJSON('playtime-settings'),'{"count":3}');
assert.throws(()=>reopened.storage.setItem('huge','x'.repeat(65537)),/Framey plugin cache is full/);
// A malformed or over-limit message from a plugin must not poison saved data.
const savedCache=values.get('framey-plugin-cache-v1:14');
reopened.send({type:'framey:cache:save',session,entries:{huge:'x'.repeat(65537)}});
assert.equal(values.get('framey-plugin-cache-v1:14'),savedCache);
reopened.send({type:'framey:cache:save',session:oldSession,entries:{poison:'yes'}});
assert.equal(values.get('framey-plugin-cache-v1:14'),savedCache);
reopened.storage.clear();
assert.equal(values.get('framey-plugin-cache-v1:14'),'{}');

// A delayed parent reply must not open the plugin with empty settings and
// later overwrite a retained snapshot. A missing reply fails visibly.
values.set('framey-plugin-cache-v1:14','{"saved":"true"}');
const delayed=iframe({delaySeed:true});
let settled=false;
const delayedWait=delayed.waitForSeed().then(()=>{settled=true;});
await Promise.resolve();
assert.equal(settled,false);
assert.equal(delayed.timers[0].ms,5000);
delayed.flushSeed();
await delayedWait;
assert.equal(delayed.storage.getItem('saved'),'true');
assert.equal(delayed.timers[0].active,false);

const missing=iframe({delaySeed:true});
const failure=assert.rejects(missing.waitForSeed(),/storage did not initialize/);
missing.timers[0].callback();
await failure;
missing.flushSeed();
assert.equal(missing.storage.getItem('saved'),null,'a late reply must not resurrect a failed panel');

const invalid=iframe({delaySeed:true});
const invalidFailure=assert.rejects(invalid.waitForSeed(),/storage returned invalid data/);
invalid.receive({type:'framey:cache:seed',session,entries:{huge:'x'.repeat(65537)}});
await invalidFailure;
assert.equal(invalid.storage.length,0);

// A saved cache that cannot be read must never masquerade as first use.
// No plugin initializer may run until a successful seed proves the snapshot.
const readableGet=localStorage.getItem;
const retainedDisk=values.get('framey-plugin-cache-v1:14');
localStorage.getItem=()=>{throw new DOMException('Blocked','SecurityError');};
const unreadable=iframe();
await assert.rejects(unreadable.waitForSeed(),/Could not read saved plugin settings/);
const readsBeforeStart=unreadable.bundleReads;
await unreadable.start();
assert.equal(unreadable.bundleReads,readsBeforeStart,'failed cache must stop startup before reading/importing the plugin bundle');
assert.match(el('frameyPanelStatus').textContent,/Plugin panel unavailable: Could not read saved plugin settings/);
assert.equal(unreadable.storage.length,0);
assert.equal(values.get('framey-plugin-cache-v1:14'),retainedDisk);
unreadable.receive({type:'framey:cache:seed',session,entries:{late:'stale'}});
assert.equal(unreadable.storage.getItem('late'),null,'late reply cannot revive failed initialization');
localStorage.getItem=readableGet;
for(const raw of ['not JSON','null','[]','{"saved":true}',
    JSON.stringify({saved:'x'.repeat(65537)}),JSON.stringify({['x'.repeat(257)]:'value'}),
    JSON.stringify(Object.fromEntries(Array.from({length:65},(_,index)=>[String(index),'value']))),
    JSON.stringify({a:'x'.repeat(50000),b:'x'.repeat(50000),c:'x'.repeat(50000)})]) {
  values.set('framey-plugin-cache-v1:14',raw);
  const damaged=iframe();
  await assert.rejects(damaged.waitForSeed(),/Could not read saved plugin settings/);
  assert.equal(damaged.storage.length,0);
  assert.equal(values.get('framey-plugin-cache-v1:14'),raw,'invalid saved bytes must remain untouched');
}
values.delete('framey-plugin-cache-v1:14');
const firstUse=iframe();await firstUse.waitForSeed();
assert.equal(firstUse.storage.length,0,'genuinely absent cache remains valid first use');
values.set('framey-plugin-cache-v1:14',retainedDisk);
const readableAgain=iframe();await readableAgain.waitForSeed();
assert.equal(readableAgain.storage.getItem('saved'),'true','reopen after recovery restores saved value');

// A full/denied browser store can still return an older saved value. Keep the
// newest valid snapshot across iframe replacement instead of restoring it.
const diskWrite=localStorage.setItem;
localStorage.setItem=()=>{throw new DOMException('Full', 'QuotaExceededError');};
const beforeDenial=iframe();
beforeDenial.storage.saved='latest';
assert.equal(values.get('framey-plugin-cache-v1:14'),'{"saved":"true"}');
assert.equal(el('frameyCacheWarning').hidden,false,'failed storage writes must be visible');
el('frameyCacheRetry').onclick();
assert.equal(el('frameyCacheWarning').hidden,false,'a failed retry must retain the notice and latest values');
assert.equal(values.get('framey-plugin-cache-v1:14'),'{"saved":"true"}');
vm.runInContext('openFrameyPanel(14,"Steam Status")',parent);
session=vm.runInContext('frameySession',parent);
const deniedReopen=iframe();
assert.equal(deniedReopen.storage.getItem('saved'),'latest');
assert.equal(deniedReopen.storage.saved,'latest','property reads must use the latest fallback snapshot');
assert.equal(el('frameyCacheWarning').hidden,false,'reopen must keep the unsaved-settings notice');
deniedReopen.send({type:'framey:scroll:result',session,direction:'down',moved:true});
deniedReopen.send({type:'framey:error',session,message:'Synthetic unrelated panel error'});
assert.equal(el('frameyCacheWarning').hidden,false,'other panel status messages must not hide failed saves');
await deniedReopen.steamStorage.SetObject('settings',{enabled:true});
deniedReopen.send({type:'framey:cache:save',session,entries:{huge:'x'.repeat(65537)}});

// Reopening another plugin cannot see the failed write or clear its cache.
vm.runInContext('deckyState.plugins.push({storeId:15,sha256:"b",version:"1"});openFrameyPanel(15,"Other")',parent);
session=vm.runInContext('frameySession',parent);
const other=iframe();
assert.equal(other.storage.getItem('saved'),null);
assert.equal(el('frameyCacheWarning').hidden,true,'another plugin must not inherit the notice');
el('frameyCacheRetry').onclick();
assert.equal(values.has('framey-plugin-cache-v1:15'),false,'retry without a failed snapshot must do nothing');
other.storage.clear();
assert.equal(el('frameyCacheWarning').hidden,false,'a failed clear must also warn');
vm.runInContext('openFrameyPanel(14,"Steam Status")',parent);
session=vm.runInContext('frameySession',parent);
const stillDenied=iframe();
assert.equal(stillDenied.storage.getItem('saved'),'latest');
assert.equal(await stillDenied.steamStorage.GetJSON('settings'),'{"enabled":true}');
delete stillDenied.storage.saved;
vm.runInContext('openFrameyPanel(14,"Steam Status")',parent);
session=vm.runInContext('frameySession',parent);
assert.equal(iframe().storage.getItem('saved'),null,'removal must also survive a denied write');

// Storage recovery flushes the latest complete snapshot; a fresh parent page
// can then read it from disk without any in-memory fallback.
localStorage.setItem=diskWrite;
el('frameyCacheRetry').onclick();
assert.equal(el('frameyCacheWarning').hidden,true,'retry must clear the notice only after durable storage succeeds');
assert.deepEqual(JSON.parse(values.get('framey-plugin-cache-v1:14')),
  {'steam-client:settings':'{"enabled":true}'},'retry must save the latest complete snapshot without an extra edit');
vm.runInContext('openFrameyPanel(15,"Other")',parent);
session=vm.runInContext('frameySession',parent);
assert.equal(el('frameyCacheWarning').hidden,false,'saving one plugin must not clear another failed snapshot');
el('frameyCacheRetry').onclick();
assert.equal(values.get('framey-plugin-cache-v1:15'),'{}','retry must persist a failed clear');
assert.equal(el('frameyCacheWarning').hidden,true);
vm.runInContext('openFrameyPanel(14,"Steam Status")',parent);
session=vm.runInContext('frameySession',parent);
assert.equal(el('frameyCacheWarning').hidden,true);
const recovered=iframe();
recovered.storage.setItem('saved','durable');
assert.deepEqual(JSON.parse(values.get('framey-plugin-cache-v1:14')),
  {'steam-client:settings':'{"enabled":true}',saved:'durable'});
recovered.storage.clear();
assert.equal(values.get('framey-plugin-cache-v1:14'),'{}');

// A valid seeded view may retain a later failed write even when both read
// and write access become unavailable. Its known snapshot takes precedence.
const beforeFullDenial=iframe();await beforeFullDenial.waitForSeed();
localStorage.setItem=()=>{throw Error('storage denied');};
const diskRead=localStorage.getItem;
localStorage.getItem=()=>{throw Error('storage denied');};
beforeFullDenial.storage.setItem('memory-only','kept');
vm.runInContext('openFrameyPanel(14,"Steam Status")',parent);
session=vm.runInContext('frameySession',parent);
assert.equal(iframe().storage.getItem('memory-only'),'kept');
localStorage.getItem=diskRead;
localStorage.setItem=diskWrite;
assert.equal(el('frameyCacheWarning').hidden,false);
iframe().storage.setItem('memory-only','now durable');
assert.equal(el('frameyCacheWarning').hidden,true,'a normal successful write also resolves the notice');
