import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const html=readFileSync(new URL('../../ui/headset.html',import.meta.url),'utf8');
const source=html.match(/<script>([\s\S]*?)<\/script>/)[1].split('refresh();refreshGames();')[0];
const elements=new Map(),requests=[],replies=[],listeners=[];
const frame={postMessage:value=>replies.push(value)};
const el=id=>{if(!elements.has(id))elements.set(id,{removeAttribute(){},scrollIntoView(){}});return elements.get(id);};
el('frameyFrame').contentWindow=frame;
const context=vm.createContext({document:{getElementById:el},location:{hash:'',pathname:'/'},
  history:{replaceState(){}},sessionStorage:{getItem:()=>null},localStorage:{getItem:()=>null},
  window:{addEventListener:(type,fn)=>listeners.push({type,fn})},setTimeout:()=>1,clearTimeout(){},
  setInterval:()=>1,clearInterval(){},console,
  fetch:(path,options)=>new Promise(resolve=>requests.push({path,body:JSON.parse(options.body),resolve}))});
vm.runInContext(source,context);
const open=()=>vm.runInContext('deckyState={running:true,plugins:[{storeId:131,sha256:"'+'a'.repeat(64)+'",version:"1.1.0"}]};openFrameyPanel(131,"Downloads")',context);
open();
const send=(data,origin=frame)=>listeners.find(x=>x.type==='message').fn({source:origin,data});
const session=vm.runInContext('frameySession',context);
const message={type:'framey:downloads',id:1,session,method:'queue',args:[[10,20],1]};
for(const value of [{...message,session:'stale'},{...message,args:[[10]]},
  {...message,args:[[10],true]},{...message,method:'ShutdownPC'}])await send(value);
await send(message,{});assert.equal(requests.length,0);
const pending=send(message);
assert.equal(requests[0].path,'/api/framey/downloads');
assert.deepEqual(JSON.parse(JSON.stringify(requests[0].body)),{id:131,receipt:'a'.repeat(64),
  session,action:'queue',appids:[10,20],revision:1});
open();
assert.equal(requests[1].body.action,'close');assert.equal(requests[1].body.session,session);
requests[0].resolve({ok:true,json:async()=>({result:{queued:2}})});await pending;
assert.equal(replies.length,0,'an old document never reports queue success in a replacement panel');
const current=vm.runInContext('frameySession',context);
const read=send({type:'framey:downloads',id:2,session:current,method:'read',args:[]});
requests.at(-1).resolve({ok:true,json:async()=>({result:{ready:true,items:[],revision:1}})});await read;
assert.equal(replies.at(-1).result.ready,true);
await send({type:'framey:downloads:close',session:'stale'});
const before=requests.length;
el('frameyClose').onclick();
assert.equal(requests.length,before+1);assert.equal(requests.at(-1).body.action,'close');
