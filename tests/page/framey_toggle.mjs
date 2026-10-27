// Exact official Pause Games component and settings callbacks; effects/process
// actions never execute here. Actual Decky discovery/RPC has a separate gate.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const bundle=readFileSync(process.argv[2],'utf8');
const official=bundle.replace(/export \{ index as default \};/,
  'window.__toggleTest = {AppItem, Settings};');
assert.notEqual(official,bundle);
const source=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8');
const host=source.replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n})();');
assert.notEqual(host,source);
const React={Fragment:'fragment',Component:class {},
  createElement:(type,props,...children)=>({type,props:props||{},children}),
  createContext:()=>({}),useState:value=>[value,()=>{}],useEffect(){},
  useRef:value=>({current:value}),useMemo:fn=>fn(),useCallback:fn=>fn};
const messages=[],listeners=[];
const parent={postMessage:message=>messages.push(message)};
const window={React,ReactDOM:{createRoot:()=>({render(){}})},location:{hash:''}};
const context=vm.createContext({window,parent,navigator:{language:'en'},
  document:{getElementById:()=>({})},console,URL,Blob,
  addEventListener:(type,handler)=>listeners.push({type,handler}),setTimeout:()=>1,clearTimeout(){}});
vm.runInContext(host,context);
Object.assign(context,{DFL:window.DFL,SP_REACT:React});
vm.runInContext(official,context,{timeout:2000});
const {AppItem,Settings}=window.__toggleTest;
const find=(node,type)=>node?.type===type?node:(node?.children||[]).flat(Infinity)
  .map(child=>find(child,type)).find(Boolean);
for(const excluded of [false,true]) {
  vm.runInContext(`window.__toggleTest.Settings.data.noAutoPauseSet=new Set(${excluded?'[424242]':'[]'});`,context);
  const row=AppItem({app:{appid:'424242',display_name:'Private fixture'},autoPause:true});
  const toggle=find(row,window.DFL.Toggle);
  assert.ok(toggle);
  const input=window.DFL.Toggle(toggle.props);
  assert.equal(input.props.checked,!excluded,'official persisted exclusion must display correctly');
  input.props.onChange({target:{checked:excluded}});
  const call=messages.at(-1);
  assert.equal(call.type,'framey:call');
  assert.equal(call.method,excluded?'remove_no_auto_pause_set':'add_no_auto_pause_set');
  assert.deepEqual(Array.from(call.args),[424242]);
  assert.equal(Settings.data.noAutoPauseSet.has(424242),!excluded);
  listeners.find(x=>x.type==='message').handler({source:parent,
    data:{type:'framey:reply',id:call.id,result:null}});
}
assert.equal(messages.filter(x=>x.type==='framey:call').length,2);
