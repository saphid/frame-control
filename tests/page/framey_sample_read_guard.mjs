import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const host=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8')
  .replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n})();');
const bundle=readFileSync(process.argv[2] || new URL('../../examples/framey-settings/dist/index.js',import.meta.url),'utf8');
let hooks=[],cursor=0;const effects=[];
const React={Fragment:'fragment',Component:class {},
  createElement:(type,props,...children)=>({type,props:props||{},children}),
  cloneElement:(element,props)=>({...element,props:{...element.props,...props}}),
  isValidElement:element=>!!element?.type,
  useState:value=>{const index=cursor++;if(!(index in hooks))hooks[index]=value;
    const state=hooks;return [state[index],value=>{state[index]=value;}];},
  useRef:value=>{const index=cursor++;return hooks[index]??={current:value};},
  useEffect:effect=>{const index=cursor++;if(!(index in hooks)){hooks[index]=true;effects.push(effect);}}};
class Element {
  constructor(){this.children=[];}
  append(...nodes){this.children.push(...nodes);}
  setAttribute(){}
  remove(){}
}
const elements=new Map(),roots=new Map(),listeners=[],calls=[];
const window={React,ReactDOM:{createRoot:node=>{
  const root={render:tree=>{root.tree=tree;},unmount(){}};roots.set(node,root);return root;
}}};
const parent={postMessage:message=>{if(message.type==='framey:call')calls.push(message);}};
const context=vm.createContext({window,document:{getElementById:id=>{
  if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},createElement:()=>new Element()},
  navigator:{language:'en'},parent,addEventListener:(type,handler)=>listeners.push({type,handler}),
  setTimeout:()=>1,clearTimeout(){}});
vm.runInContext(host,context);
Object.assign(context,{SP_REACT:window.SP_REACT,SP_JSX:window.SP_JSX,DFL:window.DFL});
vm.runInContext(bundle.replace(/export \{ index as default \};/,'window.sample=index;'),context);
const plugin=window.sample(),state=[];
const render=()=>{hooks=state;cursor=0;return plugin.content.type();};
const nodes=(tree,type)=>Array.isArray(tree)?tree.flatMap(child=>nodes(child,type)):
  [...(tree?.type===type?[tree]:[]),...(tree?.children||[]).flatMap(child=>nodes(child,type))];
const toggle=tree=>nodes(tree,window.DFL.ToggleField)[0];
const button=(tree,name)=>nodes(tree,window.DFL.ButtonItem).find(item=>item.children[0]===name);
const reply=(call,error,result)=>listeners.find(listener=>listener.type==='message').handler({source:parent,
  data:{type:'framey:reply',id:call.id,error,result}});
const settle=()=>new Promise(resolve=>setImmediate(resolve));
const writes=()=>calls.filter(call=>call.method==='set_setting');
let tree=render();
for(const effect of effects.splice(0))effect();
assert.equal(calls.at(-1).method,'get_setting');
assert.equal(toggle(tree).props.disabled,true);
reply(calls.at(-1),'Synthetic read failure');await settle();tree=render();
assert.equal(button(tree,'Reload saved setting').props.disabled,false,'read recovery stays available');
assert.match(nodes(tree,'p')[0].children[0],/Could not read setting/);
// Even callbacks retained before a redraw must not overwrite an unread value.
toggle(tree).props.onChange(false);button(tree,'Reset example setting').props.onClick();
await settle();assert.equal(writes().length,0);
assert.equal(toggle(tree).props.disabled,true,'failed initial read must not enable the default value for saving');
assert.equal(button(tree,'Reset example setting').props.disabled,true);
assert.equal(roots.get(elements.get('framey-modal')).tree,undefined);
const count=calls.length;const reload=button(tree,'Reload saved setting').props.onClick;
reload();reload();assert.equal(calls.length,count+1,'rapid recovery taps send one read');
tree=render();assert.equal(toggle(tree).props.disabled,true);
reply(calls.at(-1),undefined,true);await settle();tree=render();
assert.equal(toggle(tree).props.checked,true,'recovery displays the backend value, not the initial false default');
assert.equal(toggle(tree).props.disabled,false);

// Read-only quick actions use the same runtime contract, including real false.
const quickRead=plugin.frameyQuickActions[0].onClick;
for(const invalid of ['false',null,{}]) {
  const pending=quickRead();
  const failed=assert.rejects(pending,/invalid setting value/);
  reply(calls.at(-1),undefined,invalid);await failed;
}
const quickOff=quickRead();reply(calls.at(-1),undefined,false);
assert.equal(await quickOff,'Saved setting is off');
const quickOn=quickRead();reply(calls.at(-1),undefined,true);
assert.equal(await quickOn,'Saved setting is on');
assert.equal(button(tree,'Reset example setting').props.disabled,false);
const oldToggle=toggle(tree).props.onChange;
oldToggle(false);assert.equal(writes().length,1);
assert.deepEqual(Array.from(writes()[0].args),['enabled',false]);
reply(writes()[0],undefined,true);await settle();tree=render();
assert.equal(toggle(tree).props.checked,false);
// A failed later reload also invalidates permission to edit, even when a
// previously read value remains on screen and an older callback is retained.
button(tree,'Reload saved setting').props.onClick();oldToggle(true);
assert.equal(writes().length,1);
reply(calls.at(-1),'Synthetic reload failure');await settle();tree=render();
assert.equal(toggle(tree).props.disabled,true);
oldToggle(true);button(tree,'Reset example setting').props.onClick();
await settle();assert.equal(writes().length,1);
button(tree,'Reload saved setting').props.onClick();
reply(calls.at(-1),undefined,false);await settle();tree=render();
assert.equal(toggle(tree).props.disabled,false);
assert.equal(toggle(tree).props.checked,false);

// A rejected reply may arrive after the backend committed the write. Keep
// the displayed value untrusted until a successful read reconciles it.
const beforeRejectedSave=writes().length;
oldToggle(true);
assert.equal(writes().length,beforeRejectedSave+1);
reply(writes().at(-1),'Reply lost after commit');await settle();tree=render();
assert.equal(toggle(tree).props.checked,false,'a failed reply cannot announce the requested value as saved');
assert.equal(toggle(tree).props.disabled,true,'an ambiguous save must require a read before further edits');
assert.equal(button(tree,'Reset example setting').props.disabled,true);
assert.match(nodes(tree,'p')[0].children[0],/Reload saved setting/);
oldToggle(false);button(tree,'Reset example setting').props.onClick();await settle();
assert.equal(writes().length,beforeRejectedSave+1,'retained callbacks cannot issue a second write');
button(tree,'Reload saved setting').props.onClick();
reply(calls.at(-1),'Read still unavailable');await settle();tree=render();
assert.equal(toggle(tree).props.disabled,true,'failed reconciliation must not permit writes');
oldToggle(false);await settle();assert.equal(writes().length,beforeRejectedSave+1);
button(tree,'Reload saved setting').props.onClick();
reply(calls.at(-1),undefined,true);await settle();tree=render();
assert.equal(toggle(tree).props.checked,true,'reconciliation displays the committed value from the backend');
assert.equal(toggle(tree).props.disabled,false);
toggle(tree).props.onChange(false);
assert.equal(writes().length,beforeRejectedSave+2,'editing resumes only after successful reconciliation');
reply(writes().at(-1),undefined,true);await settle();tree=render();
assert.equal(toggle(tree).props.checked,false);

// TypeScript callable types do not validate runtime replies. A malformed read
// must not turn a truthy string/object into permission to overwrite settings.
for(const invalid of ['false',0,1,null,undefined,{},[]]) {
  button(tree,'Reload saved setting').props.onClick();
  reply(calls.at(-1),undefined,invalid);await settle();tree=render();
  assert.equal(toggle(tree).props.disabled,true,'malformed read must keep editing locked');
  assert.equal(toggle(tree).props.checked,false,'malformed read must retain the last known display');
  assert.match(nodes(tree,'p')[0].children[0],/Could not read setting/);
  const before=writes().length;
  oldToggle(true);button(tree,'Reset example setting').props.onClick();await settle();
  assert.equal(writes().length,before,'malformed read cannot authorize writes');
}
button(tree,'Reload saved setting').props.onClick();
reply(calls.at(-1),undefined,false);await settle();tree=render();
assert.equal(toggle(tree).props.disabled,false,'a real false read must enable editing');

// The sample backend promises true as its save acknowledgement. False or
// malformed resolved replies cannot be presented as a confirmed saved value.
for(const invalid of [false,null,undefined,0,1,'true',{},[]]) {
  const toasts=elements.get('framey-toasts')?.children.length||0;
  toggle(tree).props.onChange(true);
  reply(writes().at(-1),undefined,invalid);await settle();tree=render();
  assert.equal(toggle(tree).props.checked,false,'invalid save acknowledgement cannot claim requested value');
  assert.equal(toggle(tree).props.disabled,true,'invalid save acknowledgement must require reconciliation');
  assert.match(nodes(tree,'p')[0].children[0],/Could not confirm saved setting/);
  assert.equal(elements.get('framey-toasts')?.children.length||0,toasts,'unconfirmed save must not toast success');
  const before=writes().length;oldToggle(false);await settle();assert.equal(writes().length,before);
  button(tree,'Reload saved setting').props.onClick();
  reply(calls.at(-1),undefined,false);await settle();tree=render();
  assert.equal(toggle(tree).props.disabled,false);
}
toggle(tree).props.onChange(true);reply(writes().at(-1),undefined,true);await settle();tree=render();
assert.equal(toggle(tree).props.checked,true,'true save acknowledgement restores the normal success path');
assert.equal(toggle(tree).props.disabled,false);
