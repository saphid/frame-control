// Wine Cellar's exact panel uses a receipt-bound RPC facade, not a network socket.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8');
const host=source.replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n})();');
assert.notEqual(host,source);
const React={Fragment:'fragment',Component:class {},createElement:(type,props,...children)=>({type,props,children}),
  createContext:()=>({}),useState:value=>[value,()=>{}],useEffect(){},useRef:value=>({current:value}),
  useMemo:fn=>fn(),useCallback:fn=>fn};
const calls=[],listeners=[];
const parent={postMessage:message=>{
  if(message.type!=='framey:call') return;
  calls.push(message);
  let result;
  if(message.method==='framey_ws_open') result='0123456789abcdef0123456789abcdef';
  else if(message.method==='framey_ws_poll') result={messages:[JSON.stringify({type:'UpdateState',app_state:{installed_tools:[]}})],closed:true};
  else result=null;
  queueMicrotask(()=>listeners.find(x=>x.type==='message').handler({source:parent,
    data:{type:'framey:reply',id:message.id,result}}));
}};
let nativeConstructed=false;
class NativeWebSocket { constructor(){nativeConstructed=true;} }
const window={React,ReactDOM:{createRoot:()=>({render(){}})},location:{hash:''},WebSocket:NativeWebSocket};
const context=vm.createContext({window,parent,navigator:{language:'en'},
  document:{getElementById:id=>id==='framey-bundle'?{dataset:{wineSocket:'1'}}:{}},
  console,URL,Blob,EventTarget,Event,MessageEvent,DOMException,
  addEventListener:(type,handler)=>listeners.push({type,handler}),setTimeout,clearTimeout});
vm.runInContext(host,context);
assert.notEqual(window.WebSocket,NativeWebSocket);
assert.throws(()=>new window.WebSocket('ws://example.com:8887'),/unavailable/);
const events=[];
const socket=new window.WebSocket('ws://localhost:8887');
socket.onopen=()=>{events.push('open');socket.send('{"type":"GetState"}');};
socket.onmessage=event=>events.push(JSON.parse(event.data).type);
socket.onclose=()=>events.push('close');
await new Promise((resolve,reject)=>{
  const deadline=setTimeout(()=>reject(Error('Wine Cellar facade timed out')),1000);
  const check=()=>events.includes('close')?(clearTimeout(deadline),resolve()):setTimeout(check,1);
  check();
});
await new Promise(resolve=>setTimeout(resolve,10));
assert.equal(nativeConstructed,false);
assert.deepEqual(events,['open','UpdateState','close']);
assert.equal(socket.readyState,window.WebSocket.CLOSED);
assert.deepEqual(calls.map(call=>call.method),
  ['framey_ws_open','framey_ws_poll','framey_ws_send','framey_ws_close']);
