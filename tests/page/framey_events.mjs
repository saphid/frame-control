import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source=readFileSync(new URL('../../ui/framey-events.js',import.meta.url),'utf8');
const handlers=new Set(),timers=new Map();let now=1000,nextTimer=0;
const backend={addEventListener(name,listener){assert.equal(name,'loader/plugin_event');handlers.add(listener);},
  removeEventListener(name,listener){assert.equal(name,'loader/plugin_event');handlers.delete(listener);}};
const window={DeckyBackend:backend};
const context=vm.createContext({window,Date:{now:()=>now},
  setInterval:fn=>{timers.set(++nextTimer,fn);return nextTimer;},clearInterval:id=>timers.delete(id)});
const poll=(session='one',name='Simple Timer',events=['tick'],cursor=0)=>
  JSON.parse(JSON.stringify(vm.runInContext(source,context)({session,name,events,cursor})));
const emit=(plugin,event,...args)=>{for(const handler of handlers)handler({plugin,event,args});};
assert.deepEqual(poll(),{events:[],cursor:0});
assert.equal(handlers.size,1);
emit('Other plugin','tick',10);emit('Simple Timer','other',99);emit('Simple Timer','tick',42,'seconds');
assert.deepEqual(poll().events,[{sequence:1,event:'tick',args:[42,'seconds']}]);
assert.equal(handlers.size,1); // Polling never duplicates the backend subscription.
assert.deepEqual(poll('one','Simple Timer',['tick'],1).events,[]);
assert.equal(poll().events.length,1); // Retry a lost HTTP response without losing its event.
assert.throws(()=>poll('one','Another plugin'),/belongs to another plugin/);
poll('two','Another plugin');emit('Another plugin','tick',123);
assert.deepEqual(poll('two','Another plugin').events[0].args,[123]);
assert.equal(poll().events.length,1);
emit('Simple Timer','tick','x'.repeat(8193));assert.equal(poll().events.length,1);
for(let index=0;index<100;index++)emit('Simple Timer','tick',index);
assert.equal(poll().events.length,64);
assert.equal(poll().events.at(-1).args[0],99);
for(let index=0;index<20;index++)emit('Simple Timer','tick','x'.repeat(8000));
assert.ok(JSON.stringify(poll()).length<50*1024);
poll('one','Simple Timer',[]);assert.equal(handlers.size,1);
now+=16000;for(const timer of [...timers.values()])timer();
assert.equal(handlers.size,0);assert.equal(timers.size,0);
poll();assert.equal(handlers.size,1);
// A Decky frontend reconnect must register against the replacement backend.
let replaced=0;
window.DeckyBackend={...backend,addEventListener(name,fn){replaced++;backend.addEventListener(name,fn);}};
poll();assert.equal(replaced,1);assert.equal(handlers.size,1);
poll('one','Simple Timer',[]);assert.equal(handlers.size,0);

// Output is scoped to both the actual plugin and the selected Terminal ID.
poll('terminal','Decky Terminal',['terminal_output#private-pty']);
emit('Other plugin','terminal_output#private-pty','wrong plugin');
emit('Decky Terminal','terminal_output#another-pty','wrong terminal');
emit('Decky Terminal','terminal_output#private-pty','private output');
assert.deepEqual(poll('terminal','Decky Terminal',['terminal_output#private-pty']).events,
  [{sequence:1,event:'terminal_output#private-pty',args:['private output']}]);
poll('terminal','Decky Terminal',[]);assert.equal(handlers.size,0);
