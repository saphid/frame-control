import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const host=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8')
  .replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n})();');
const React={Fragment:'fragment',Component:class {},forwardRef:render=>render,
  createElement:(type,props,...children)=>({type,props:{...props,
    ...(children.length?{children:children.length===1?children[0]:children}:{})},children}),
  cloneElement:(element,props)=>({...element,props:{...element.props,...props}}),
  useState:value=>[value,()=>{}],useRef:value=>({current:value}),
  useEffect(){},useImperativeHandle(){},isValidElement:value=>!!value?.type};
const elements=new Map(),roots=new Map();
const window={React,ReactDOM:{createRoot:node=>{
  const root={render(value){this.value=value;}};roots.set(node,root);return root;
}},addEventListener(){}};
const context=vm.createContext({window,document:{getElementById:id=>{
  if(!elements.has(id))elements.set(id,{});return elements.get(id);}},
  navigator:{language:'en'},parent:{postMessage(){}},addEventListener(){},setTimeout(){},clearTimeout(){}});
vm.runInContext(host,context);
const nodes=(tree,type)=>Array.isArray(tree)?tree.flatMap(child=>nodes(child,type)):
  [...(tree?.type===type?[tree]:[]),...(tree?.children||[]).flatMap(child=>nodes(child,type))];

// Decky callbacks receive the original React event. Preserve uncontrolled
// drafts and suppress callbacks on disabled fields, including direct calls.
const events=[];
const handlers=Object.fromEntries(['onChange','onBlur','onFocus','onClick','onKeyDown','onKeyUp']
  .map(name=>[name,event=>events.push([name,event])]));
const field=nodes(window.DFL.TextField({defaultValue:'Saved',...handlers}),'input')[0];
assert.equal(field.props.defaultValue,'Saved');
assert.equal(field.props.value,undefined);
const event={target:{value:'Edited'},key:'Enter'};
for(const name of Object.keys(handlers))field.props[name](event);
assert.equal(events.length,6);
for(const [index,name] of Object.keys(handlers).entries()){
  assert.equal(events[index][0],name);assert.equal(events[index][1],event);
}
const disabled=nodes(window.DFL.TextField({disabled:true,...handlers}),'input')[0];
for(const name of Object.keys(handlers))disabled.props[name](event);
assert.equal(events.length,6);
const controlled=nodes(window.DFL.TextField({value:'Current',defaultValue:'Old'}),'input')[0];
assert.equal(controlled.props.value,'Current');
assert.equal(controlled.props.defaultValue,undefined,'controlled fields must not also receive a default');

// Replay only this function from the digest-verified Game Sync 1.0.4 archive.
// No backend, cloud config, rclone process, file operation or network runs.
const frontend=readFileSync(process.argv[2],'utf8');
const popup=frontend.match(/function textInputPopup\(title, value, onOK\) \{[\s\S]*?\n\}/)?.[0];
assert.ok(popup,'published Game Sync text dialog must be present');
Object.assign(context,{DFL:window.DFL,SP_JSX:window.SP_JSX});
vm.runInContext(popup,context);
context.commits=[];
vm.runInContext('textInputPopup("Private label", "Original", value=>commits.push(value))',context);
const modal=()=>roots.get(elements.get('framey-modal')).value[0].children[1];
let rendered=modal().type(modal().props);
const inputElement=nodes(rendered,window.DFL.TextField)[0];
const input=nodes(inputElement.type(inputElement.props),'input')[0];
assert.equal(input.props.defaultValue,'Original');
input.props.onBlur({target:{value:'Edited private label'}});
assert.equal(context.commits.length,0,'blur updates the draft without committing the modal');
nodes(rendered,'button').find(button=>button.children[0]==='OK').props.onClick();
assert.deepEqual(Array.from(context.commits),['Edited private label']);
assert.equal(roots.get(elements.get('framey-modal')).value,null);
vm.runInContext('textInputPopup("Private label", "Keep", value=>commits.push(value))',context);
rendered=modal().type(modal().props);
nodes(rendered,'button').find(button=>button.children[0]==='Cancel').props.onClick();
assert.deepEqual(Array.from(context.commits),['Edited private label'],'cancel must not save a draft');
