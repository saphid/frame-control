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
function fixture(enabled) {
  const calls=[],listeners=[];
  let nativeCalls=0, reply={success:true,result:{status:200,body:'{"privateFixture":true}',headers:{'content-type':'application/json'}}};
  const parent={postMessage:message=>{
    if(message.type!=='framey:call')return;
    calls.push(message);
    queueMicrotask(()=>listeners.find(x=>x.type==='message').handler({source:parent,
      data:{type:'framey:reply',id:message.id,result:reply}}));
  }};
  const nativeFetch=async()=>{nativeCalls++;throw Error('Native network denied');};
  const window={React,ReactDOM:{createRoot:()=>({render(){}})},location:{hash:''},fetch:nativeFetch};
  vm.runInContext(host,vm.createContext({window,parent,navigator:{language:'en'},
    document:{getElementById:id=>id==='framey-bundle'?{dataset:{syncthingHttp:enabled?'1':'0'}}:{}},
    console,URL,Blob,Headers,Response,EventTarget,Event,MessageEvent,DOMException,
    addEventListener:(type,handler)=>listeners.push({type,handler}),setTimeout,clearTimeout}));
  return {window,calls,nativeFetch,nativeCalls:()=>nativeCalls,setReply:value=>{reply=value;}};
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
