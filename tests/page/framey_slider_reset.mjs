import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8');
const host=source.replace(/\n  start\(\);\n\}\)\(\);\s*$/,
  '\n  window.__legacy=legacyServerAPI;\n})();');
assert.notEqual(host,source);
const React={Fragment:'fragment',Component:class {},forwardRef:render=>render,
  createElement:(type,props,...children)=>({type,props:props||{},children})};
const window={React,ReactDOM:{createRoot:()=>({render(){}})},location:{hash:'#slider-reset'}};
const messages=[], listeners=[];
const parent={postMessage:message=>messages.push(message)};
const context=vm.createContext({window,parent,document:{getElementById:()=>({})},
  navigator:{language:'en'},DOMException,
  addEventListener:(type,handler)=>listeners.push({type,handler}),
  setTimeout:()=>1,clearTimeout(){}});
vm.runInContext(host,context);
const nodes=(tree,type)=>Array.isArray(tree)?tree.flatMap(child=>nodes(child,type)):
  [...(tree?.type===type?[tree]:[]),...(tree?.children||[]).flatMap(child=>nodes(child,type))];
const published=readFileSync(0,'utf8');
Object.assign(context,{deckyFrontendLib:window.DFL,lookback:7,
  setLookback:value=>{context.lookback=value;},setData:value=>{context.history=value;},
  serverAPI:window.__legacy});
const control=()=>vm.runInContext(published,context);
let element=control();
assert.equal(element.props.value,7);
assert.equal(element.props.resetValue,1);
let rendered=element.type(element.props);
const reset=nodes(rendered,'button').find(button=>button.children[0]==='Reset');
assert.ok(reset,'published resetValue must expose a usable reset control');
assert.equal(reset.props['aria-label'],'Reset Lookback in days');
reset.props.onClick();
assert.equal(context.lookback,1,'published callback receives its reset value');
const call=messages.find(message=>message.type==='framey:call');
assert.equal(call.method,'get_recent_data');
assert.equal(call.legacy,true);
assert.deepEqual(JSON.parse(JSON.stringify(call.args)),[{lookback:1}]);
const reply=listeners.find(listener=>listener.type==='message').handler;
reply({source:parent,data:{type:'framey:reply',id:call.id,
  result:{success:true,result:[{fixture:true}]}}});
for(let i=0;i<12;i++)await Promise.resolve();
assert.deepEqual(context.history,[{fixture:true}]);
element=control();rendered=element.type(element.props);
assert.equal(nodes(rendered,'input')[0].props.value,1,'redrawn control reflects the reset');
// Reset follows the same disabled and numeric bounds as the setting control.
const callsBefore=messages.length;
const locked=nodes(element.type({...element.props,disabled:true}),'button')[0];
assert.equal(locked.props.disabled,true);locked.props.onClick();
assert.equal(messages.length,callsBefore);
for(const resetValue of [undefined,NaN,Infinity,0,8])
  assert.equal(nodes(element.type({...element.props,resetValue}),'button').length,0);
// Fractional defaults remain numbers and work without a text value display.
const values=[];
const fractional=window.DFL.SliderField({value:0.9,min:0,max:1,step:0.05,
  resetValue:0.35,showValue:false,onChange:value=>values.push(value)});
nodes(fractional,'button')[0].props.onClick();
assert.deepEqual(values,[0.35]);
