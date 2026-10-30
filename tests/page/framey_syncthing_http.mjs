// The original Syncthing URLs use legacy RPC; no native network is available.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8');
const host=source.replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n})();');
assert.notEqual(host,source);
const React={Fragment:'fragment',Component:class {},createElement:(type,props,...children)=>({type,props,children}),
  createContext:()=>({}),useState:value=>[value,()=>{}],useEffect(){},useRef:value=>({current:value}),
  useMemo:fn=>fn(),useCallback:fn=>fn};
function fixture(enabled, {defer=false, clock=null}={}) {
  const calls=[],listeners=[],replies=[];
  let nativeCalls=0, reply={success:true,result:{status:200,body:'{"privateFixture":true}',headers:{'content-type':'application/json'}}};
  const parent={postMessage:message=>{
    if(message.type!=='framey:call')return;
    calls.push(message);
    const respond=()=>listeners.find(x=>x.type==='message').handler({source:parent,
      data:{type:'framey:reply',id:message.id,result:reply}});
    if(defer)replies.push(respond);else queueMicrotask(respond);
  }};
  const nativeFetch=async()=>{nativeCalls++;throw Error('Native network denied');};
  const window={React,ReactDOM:{createRoot:()=>({render(){}})},location:{hash:''},fetch:nativeFetch};
  vm.runInContext(host,vm.createContext({window,parent,navigator:{language:'en'},
    document:{getElementById:id=>id==='framey-bundle'?{dataset:{syncthingHttp:enabled?'1':'0'}}:{}},
    console,URL,Blob,Headers,Response,EventTarget,Event,MessageEvent,DOMException,
    addEventListener:(type,handler)=>listeners.push({type,handler}),setTimeout:clock?.setTimeout||setTimeout,
    clearTimeout:clock?.clearTimeout||clearTimeout,Date:clock?.Date||Date}));
  return {window,calls,nativeFetch,nativeCalls:()=>nativeCalls,setReply:value=>{reply=value;},replyNext:()=>{assert.ok(replies.length);replies.shift()();}};
}
const disabled=fixture(false);
assert.equal(disabled.window.fetch,disabled.nativeFetch);
const f=fixture(true), base='http://127.0.0.1:58384/';
assert.notEqual(f.window.fetch,f.nativeFetch);
assert.deepEqual(await (await f.window.fetch(base+'rest/db/status?folder=private%20fixture',
  {headers:{'X-API-Key':'private-fixture',Accept:'application/json'}})).json(),{privateFixture:true});
assert.equal(f.calls[0].legacy,true);
assert.equal(f.calls[0].method,'framey_http_fetch');
assert.deepEqual(JSON.parse(JSON.stringify(f.calls[0].args)),[
  {method:'GET',path:'/rest/db/status?folder=private%20fixture',headers:{accept:'application/json','x-api-key':'private-fixture'}}]);
for(const [input,init] of [
  ['https://127.0.0.1:58384/rest/system/status',{}],['http://localhost:58384/',{}],
  ['http://127.0.0.1:58384@other/',{}],[base+'#fragment',{}],
  [base,{method:'DELETE'}],[base,{body:'unavailable'}],[base,{headers:{Host:'other'}}],
  [base,{signal:AbortSignal.abort()}]]) {
  const count=f.calls.length;
  await assert.rejects(f.window.fetch(input,init));
  assert.equal(f.calls.length,count);
}
f.setReply({success:true,result:{status:204,body:'',headers:{'content-type':''}}});
assert.equal((await f.window.fetch(base+'__decky-watchdog/start',{method:'POST'})).status,204);
f.setReply({success:true,result:{status:401,body:'private fixture refused',headers:{'content-type':'text/plain'}}});
assert.equal((await f.window.fetch(base+'rest/system/status')).ok,false);
f.setReply({success:false,result:'Owned helper unavailable'});
await assert.rejects(f.window.fetch(base+'rest/system/status'),/Owned helper unavailable/);
f.setReply({success:true,result:{status:200,body:42,headers:{'content-type':''}}});
await assert.rejects(f.window.fetch(base+'rest/system/status'),/Invalid Syncthing/);
assert.equal(f.nativeCalls(),0);

// Preserve the exact five-request dashboard burst without backend overlap.
const flush=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
const serial=fixture(true,{defer:true});
const burst=Array.from({length:5},(_,i)=>serial.window.fetch(base+'rest/config/'+i));
assert.equal(serial.calls.length,1);
for(let i=0;i<5;i++){
  assert.equal(serial.calls.length,i+1);
  serial.replyNext();await flush();
}
await Promise.all(burst);
assert.deepEqual(serial.calls.map(x=>x.args[0].path),Array.from({length:5},(_,i)=>'/rest/config/'+i));

// A rejected RPC frees the slot, while cancellation of an active fetch does
// not release it until its backend reply arrives.
const cancel=fixture(true,{defer:true}),controller=new AbortController();
const active=cancel.window.fetch(base,{signal:controller.signal});
const queuedController=new AbortController();
const removed=cancel.window.fetch(base+'removed',{signal:queuedController.signal});
const next=cancel.window.fetch(base+'next');
const removedCheck=assert.rejects(removed,{name:'AbortError'});
queuedController.abort();controller.abort();await flush();
assert.equal(cancel.calls.length,1);
cancel.replyNext();await assert.rejects(active,{name:'AbortError'});await flush();
assert.equal(cancel.calls.length,2);assert.equal(cancel.calls[1].args[0].path,'/next');
cancel.setReply({success:false,result:'Owned helper unavailable'});cancel.replyNext();
await assert.rejects(next,/Owned helper unavailable/);await removedCheck;

const bounded=fixture(true,{defer:true});
const pending=Array.from({length:17},()=>bounded.window.fetch(base));
await assert.rejects(bounded.window.fetch(base),/queue is full/);
assert.equal(bounded.calls.length,1);
for(let i=0;i<17;i++){bounded.replyNext();await flush();}
await Promise.all(pending);

// Queue waiting and active RPCs each remain bounded; expired waiting work never sends.
let now=0,nextTimer=0;const timers=new Map();
const clock={Date:{now:()=>now},setTimeout:(fn,delay)=>{timers.set(++nextTimer,{fn,at:now+delay});return nextTimer;},
  clearTimeout:id=>timers.delete(id)};
const deadline=fixture(true,{defer:true,clock});
const slow=deadline.window.fetch(base),expired=deadline.window.fetch(base+'expired');
const slowCheck=assert.rejects(slow,/timed out/),expiredCheck=assert.rejects(expired,/timed out/);
now=31000;
for(const [id,timer] of [...timers])if(timer.at<=now){timers.delete(id);timer.fn();}
await flush();await slowCheck;await expiredCheck;
assert.equal(deadline.calls.length,1);assert.equal(timers.size,0);
assert.equal(serial.nativeCalls()+cancel.nativeCalls()+bounded.nativeCalls()+deadline.nativeCalls(),0);

// The real production-parent replay completes a six-read burst in over
// 30 seconds even though each RPC succeeds quickly. Queue waiting must not
// leave the later dashboard reads only the remainder of another call's budget.
now=0;
const dashboard=fixture(true,{defer:true,clock});
const dashboardReads=Array.from({length:6},(_,i)=>dashboard.window.fetch(base+'rest/dashboard/'+i));
const dashboardResult=Promise.all(dashboardReads);dashboardResult.catch(()=>{});
for(let i=0;i<6;i++){
  now+=5500;
  for(const [id,timer] of [...timers])if(timer.at<=now){timers.delete(id);timer.fn();}
  await flush();dashboard.replyNext();await flush();
}
await dashboardResult;
assert.equal(now,33000);assert.equal(dashboard.calls.length,6);assert.equal(timers.size,0);

now=0;
const remaining=fixture(true,{defer:true,clock});
const first=remaining.window.fetch(base),second=remaining.window.fetch(base+'second');
now=10000;remaining.replyNext();await first;await flush();
assert.equal(remaining.calls.length,2);
assert.deepEqual([...timers.values()].map(timer=>timer.at),[40000]);
remaining.replyNext();await second;await flush();assert.equal(timers.size,0);
