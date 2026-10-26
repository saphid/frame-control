import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const html=readFileSync(new URL('../../ui/headset.html',import.meta.url),'utf8');
const source=html.match(/<script>([\s\S]*?)<\/script>/)[1].split('refresh();refreshGames();')[0];
const elements=new Map(),listeners=[],requests=[],replies=[];
const el=id=>{if(!elements.has(id))elements.set(id,{removeAttribute(){},scrollIntoView(){}});return elements.get(id);};
const frame={postMessage:data=>replies.push(data)};
el('frameyFrame').contentWindow=frame;
const context=vm.createContext({document:{getElementById:el,createElement:()=>({})},
  location:{hash:'',pathname:'/'},history:{replaceState(){}},
  sessionStorage:{getItem:()=>null,setItem(){}},localStorage:{getItem:()=>null,setItem(){}},
  window:{addEventListener:(type,fn)=>listeners.push({type,fn})},
  setTimeout(){},setInterval(){},console,
  fetch:(path,options)=>new Promise(resolve=>requests.push({path,body:JSON.parse(options.body),resolve}))});
vm.runInContext(source,context);
vm.runInContext('deckyState={running:true,plugins:[{storeId:96,sha256:"'+'a'.repeat(64)+'",version:"1"}]};openFrameyPanel(96,"Timer")',context);
let session=vm.runInContext('frameySession',context);
const onMessage=listeners.find(x=>x.type==='message').fn;
const send=(data,origin=frame)=>onMessage({source:origin,data});
const subscription={type:'framey:events',id:1,session,args:[['tick'],0]};
await send({...subscription,session:'old'});
await send(subscription,{});
await send({...subscription,args:[['bad event'],0]});
assert.equal(requests.length,0);
const first=send(subscription);
assert.equal(requests.length,1);
assert.equal(requests[0].path,'/api/framey/events');
assert.equal(requests[0].body.id,96);
assert.equal(requests[0].body.receipt,'a'.repeat(64));
assert.equal(requests[0].body.session,session);
// WindowProxy survives navigation: stale same-plugin replies need a session check.
vm.runInContext('openFrameyPanel(96,"Timer")',context);
const secondSession=vm.runInContext('frameySession',context);
assert.notEqual(secondSession,session);
assert.equal(requests[1].body.events.length,0); // Closes only the original subscription.
assert.equal(requests[1].body.session,session);
assert.equal(requests[1].body.receipt,'a'.repeat(64));
requests[0].resolve({ok:true,json:async()=>({events:[{event:'tick',args:[42]}],cursor:1})});
await first;assert.equal(replies.length,0);
await send({type:'framey:call',id:2,session,method:'cancel_timer',args:[]});
assert.equal(requests.length,2); // Old document cannot call a newly opened plugin.
session=secondSession;
const second=send({...subscription,id:3,session});
requests[2].resolve({ok:true,json:async()=>({events:[{event:'tick',args:[7]}],cursor:2})});
await second;
assert.equal(replies.length,1);assert.equal(replies[0].result.events[0].args[0],7);
el('frameyClose').onclick();
assert.equal(requests[3].body.session,session);assert.equal(requests[3].body.events.length,0);
for(const request of requests.slice(1))request.resolve({ok:true,json:async()=>({events:[],cursor:0})});

// Only explicit zero-argument Steam reads reach the trusted parent endpoint.
vm.runInContext('openFrameyPanel(96,"Timer")',context);
session=vm.runInContext('frameySession',context);
const steamRead={type:'framey:steam',id:10,session,method:'GetIPCountry',args:[]};
const initialCount=requests.length;
for(const change of [{method:'ShutdownPC'},{method:'User.GetIPCountry'},{args:['injected']},{session:'stale'}])
  await send({...steamRead,...change});
await send(steamRead,{});
assert.equal(requests.length,initialCount);
const read=send(steamRead);
assert.equal(requests.at(-1).path,'/api/framey/steam');assert.equal(requests.at(-1).body.id,96);
assert.equal(requests.at(-1).body.receipt,'a'.repeat(64));
requests.at(-1).resolve({ok:true,json:async()=>({result:'AU'})});
await read;assert.equal(replies.at(-1).result,'AU');
const staleRead=send({...steamRead,id:11});
vm.runInContext('openFrameyPanel(96,"Timer")',context);
const priorReplies=replies.length;
requests.at(-1).resolve({ok:true,json:async()=>({result:'AU'})});
await staleRead;assert.equal(replies.length,priorReplies);
// Running reads are tied to the current iframe and session, with no method path.
session=vm.runInContext('frameySession',context);
const running={type:'framey:running',id:20,session,args:[0]};
const beforeRunning=requests.length;
for(const change of [{session:'old'},{args:[-1]},{args:[true]},{args:[0,'extra']}])
  await send({...running,...change});
await send(running,{});assert.equal(requests.length,beforeRunning);
const pendingRunning=send(running);
assert.equal(requests.at(-1).path,'/api/framey/running');
assert.equal(requests.at(-1).body.active,true);
assert.equal(requests.at(-1).body.receipt,'a'.repeat(64));
const oldRunning=requests.at(-1);
vm.runInContext('openFrameyPanel(96,"Timer")',context);
assert.equal(requests.at(-1).body.active,false);
assert.equal(requests.at(-1).body.receipt,'a'.repeat(64));
assert.equal(requests.at(-1).body.session,session);
const beforeStaleReply=replies.length;
oldRunning.resolve({ok:true,json:async()=>({result:{apps:[],events:[],cursor:0}})});
await pendingRunning;assert.equal(replies.length,beforeStaleReply);
session=vm.runInContext('frameySession',context);
const finalRunning=send({...running,id:21,session});
requests.at(-1).resolve({ok:true,json:async()=>({result:{apps:[],events:[],cursor:0}})});
await finalRunning;
await send({type:'framey:running:close',session});
assert.equal(requests.at(-1).body.receipt,'a'.repeat(64));
assert.equal(requests.at(-1).body.active,false);

const scrollSession=vm.runInContext('frameySession',context);
el('frameyScrollDown').onclick();
assert.equal(replies.at(-1).type,'framey:scroll');
assert.equal(replies.at(-1).session,scrollSession);
assert.equal(replies.at(-1).direction,'down');
await send({type:'framey:scroll:result',session:'old',direction:'down',moved:true});
assert.equal(el('frameyPanelStatus').textContent,'Loading plugin panel…');
await send({type:'framey:scroll:result',session:scrollSession,direction:'down',moved:true});
assert.equal(el('frameyPanelStatus').textContent,'Scrolled plugin down');
await send({type:'framey:scroll:result',session:scrollSession,direction:'down',moved:false});
assert.equal(el('frameyPanelStatus').textContent,'No more plugin content in that direction');
// WindowProxy also survives panel navigation for lifecycle and input messages.
// An old iframe must not mark a replacement ready, hide its error, or record
// controller evidence for the new panel.
const beforeStatusRequests=requests.length;
for(const type of ['framey:ready','framey:input','framey:error']) {
  await send({type,session:'old',message:'old panel failed'});
  await send({type,message:'missing session'});
}
assert.equal(requests.length,beforeStatusRequests);
assert.equal(el('frameyPanelStatus').textContent,'No more plugin content in that direction');
await send({type:'framey:ready',session:scrollSession});
assert.equal(el('frameyPanelStatus').textContent,'Plugin panel ready');
assert.equal(requests.at(-1).path,'/api/framey/check');
assert.equal(requests.at(-1).body.kind,'panel');
await send({type:'framey:input',session:scrollSession});
assert.equal(requests.at(-1).body.kind,'input');
await send({type:'framey:error',session:scrollSession,message:'current panel failed'});
assert.equal(el('frameyPanelStatus').textContent,'Plugin panel unavailable: current panel failed');
el('frameyClose').onclick();
const replyCount=replies.length;
el('frameyScrollUp').onclick();
assert.equal(replies.length,replyCount);
