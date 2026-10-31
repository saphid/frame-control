// The exact published Terminal subscribes to terminal_output#<id>. Exercise the
// shipped frontend event API, including removal, without a shell or a headset.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8');
const host=source.replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n})();');
assert.notEqual(host,source);
const React={Fragment:'fragment',Component:class {},createElement(){},createContext:()=>({})};
const messages=[],listeners=[],timers=new Map();let timerId=0;
const parent={postMessage:message=>messages.push(message)};
const window={React,ReactDOM:{createRoot:()=>({render(){}})},location:{hash:'#private'}};
const context=vm.createContext({window,parent,navigator:{language:'en'},
  document:{getElementById:()=>({})},console,URL,Blob,
  addEventListener:(type,handler)=>listeners.push({type,handler}),
  setTimeout:fn=>{timers.set(++timerId,fn);return timerId;},clearTimeout:id=>timers.delete(id)});
vm.runInContext(host,context);
const api=window.__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit.connect(1,'Decky Terminal');
const received=[];const handler=value=>received.push(value);
const event='terminal_output#private-pty';
assert.equal(api.addEventListener(event,handler),handler);
const subscription=messages.at(-1);
assert.equal(subscription.type,'framey:events');
assert.deepEqual(Array.from(subscription.args[0]),[event]);
const reply=listeners.find(v=>v.type==='message').handler;
reply({source:parent,data:{type:'framey:reply',id:subscription.id,
  result:{events:[{sequence:1,event,args:['private output\r\n']}],cursor:1}}});
await new Promise(resolve=>setImmediate(resolve));
assert.deepEqual(received,['private output\r\n']);
for(const name of ['bad event','bad\nevent','event"injection','x'.repeat(129)])
  assert.throws(()=>api.addEventListener(name,handler),/Invalid Decky event listener/);
api.removeEventListener(event,handler);
await new Promise(resolve=>setImmediate(resolve));
const closed=messages.at(-1);
assert.equal(closed.type,'framey:events');assert.deepEqual(Array.from(closed.args[0]),[]);
reply({source:parent,data:{type:'framey:reply',id:closed.id,result:{events:[],cursor:0}}});
await new Promise(resolve=>setImmediate(resolve));
