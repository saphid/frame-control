import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const html=readFileSync(new URL('../../ui/headset.html',import.meta.url),'utf8');
const parentSource=html.match(/<script>([\s\S]*?)<\/script>/)[1].split('refresh();refreshGames();')[0];
const hostSource=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8')
  .replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n})();');
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
vm.runInContext('deckyState={plugins:[{storeId:14}]};openFrameyPanel(14,"Steam Status")',parent);
let session=vm.runInContext('frameySession',parent);
const firstURL=new URL(el('frameyFrame').src,'http://127.0.0.1');
const onParent=parentListeners.find(x=>x.type==='message').fn;

function iframe(){
  const listeners=[];const queued=[];let live=false;
  const frameWindow={location:{hash:`#${session}`},React:{Fragment:'fragment',Component:class {},createElement:()=>({}),isValidElement:()=>true},
    ReactDOM:{createRoot:()=>({render(){}})}};
  const proxy={postMessage:message=>listeners.find(x=>x.type==='message')?.fn({source:hostParent,data:message})};
  el('frameyFrame').contentWindow=proxy;
  const hostParent={postMessage:message=>live?onParent({source:proxy,data:message}):queued.push(message)};
  const context=vm.createContext({window:frameWindow,document:{getElementById:()=>({})},
    navigator:{language:'en'},parent:hostParent,DOMException,
    addEventListener:(type,fn)=>listeners.push({type,fn}),setTimeout(){},clearTimeout(){}});
  vm.runInContext(hostSource,context);
  for(const message of queued)onParent({source:proxy,data:message});
  live=true;
  const send=message=>onParent({source:proxy,data:message});
  return {storage:frameWindow.localStorage,steamStorage:frameWindow.SteamClient.Storage,send};
}
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
