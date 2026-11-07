import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8');
const host=source.replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n})();');
assert.notEqual(host,source);
const React={Fragment:'fragment',Component:class {},
  createElement:(type,props,...children)=>({type,props:props||{},children}),
  useRef:value=>({current:value}),useState:value=>[value,()=>{}]};
const window={React,ReactDOM:{createRoot:()=>({render(){}})}};
const context=vm.createContext({window,document:{getElementById:()=>({})},
  navigator:{language:'en'},parent:{postMessage:message=>assert.equal(message.type,'framey:cache:init')},
  addEventListener(){},setTimeout(){},clearTimeout(){}});
// Host initialization sends only its storage initialization request.
vm.runInContext(host,context);
Object.assign(context,{DFL:window.DFL,search:'Private fixture game',
  setSearch:value=>{context.search=value;}});
// Evaluate only the exact published search control, never its initializer,
// backend, installed-app enumeration, helper process or compatibility actions.
const control=readFileSync(0,'utf8');
const nodes=(tree,type)=>Array.isArray(tree)?tree.flatMap(child=>nodes(child,type)):
  [...(tree?.type===type?[tree]:[]),...(tree?.children||[]).flatMap(child=>nodes(child,type))];
const element=vm.runInContext(control,context);
let rendered=element.type(element.props);
let input=nodes(rendered,'input')[0];
const clear=nodes(rendered,'button').find(button=>button.children.includes('Clear'));
assert.ok(clear,'the published bShowClearAction flag must expose a clear action');
assert.equal(clear.props.type,'button');
assert.equal(clear.props.disabled,false);
assert.equal(input.props['aria-label'],'Search installed Steam games and non-Steam shortcuts');
assert.equal(input.props.placeholder,'Search games, shortcuts, or tools');
assert.equal(input.props.value,'Private fixture game');
input.props.onChange({currentTarget:{value:'Edited fixture search'}});
assert.equal(context.search,'Edited fixture search');
rendered=element.type({...element.props,disabled:true});
input=nodes(rendered,'input')[0];
assert.equal(nodes(rendered,'button')[0].props.disabled,true);
assert.equal(input.props['aria-label'],element.props['aria-label']);
assert.equal(input.props.disabled,true);
input.props.onChange({currentTarget:{value:'Must not change'}});
assert.equal(context.search,'Edited fixture search');
// A visible label continues to name ordinary fields; an explicit accessible
// name is optional and does not replace the visible label or input value.
const plain=window.DFL.TextField({label:'Alias',value:'Saved alias'});
assert.equal(nodes(plain,'input')[0].props['aria-label'],undefined);
const named=window.DFL.TextField({label:'Alias','aria-label':'Device alias',value:'Saved alias'});
assert.equal(named.props.label,'Alias');
assert.equal(nodes(named,'input')[0].props['aria-label'],'Device alias');
assert.equal(nodes(named,'input')[0].props.value,'Saved alias');
