// Built author sample + real host, with delayed synthetic backend replies.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const host=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8')
  .replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n})();');
const bundle=readFileSync(new URL('../../examples/framey-settings/dist/index.js',import.meta.url),'utf8');
let current,cursor=0;
const React={Fragment:'fragment',Component:class {},
  createElement:(type,props,...children)=>({type,props:props||{},children}),
  cloneElement:(element,props)=>({...element,props:{...element.props,...props}}),
  isValidElement:element=>!!element?.type,
  useState:value=>{const owner=current,index=cursor++;if(!(index in owner.hooks))owner.hooks[index]=value;
    return [owner.hooks[index],value=>{owner.updates++;owner.hooks[index]=value;}];},
  useRef:value=>{const index=cursor++;return current.hooks[index]??={current:value};},
  useEffect:effect=>{const index=cursor++;if(!(index in current.hooks)){
    current.hooks[index]=true;current.effects.push(effect);}}};
class Element {constructor(){this.children=[];}append(...nodes){this.children.push(...nodes);}setAttribute(){}remove(){}}
const elements=new Map(),roots=new Map(),listeners=[],calls=[];
const window={React,ReactDOM:{createRoot:node=>{
  const root={render:tree=>{root.tree=tree;},unmount(){}};roots.set(node,root);return root;
}}};
const parent={postMessage:message=>{if(message.type==='framey:call')calls.push(message);}};
const context=vm.createContext({window,parent,navigator:{language:'en'},
  document:{getElementById:id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},createElement:()=>new Element()},
  addEventListener:(type,handler)=>listeners.push({type,handler}),setTimeout:()=>1,clearTimeout(){}});
vm.runInContext(host,context);
Object.assign(context,{SP_REACT:window.SP_REACT,SP_JSX:window.SP_JSX,DFL:window.DFL});
vm.runInContext(bundle.replace(/export \{ index as default \};/,'window.sample=index;'),context);
const plugin=window.sample();
const nodes=(tree,type)=>Array.isArray(tree)?tree.flatMap(child=>nodes(child,type)):
  [...(tree?.type===type?[tree]:[]),...(tree?.children||[]).flatMap(child=>nodes(child,type))];
const toggle=tree=>nodes(tree,window.DFL.ToggleField)[0];
const button=(tree,text)=>nodes(tree,window.DFL.ButtonItem).find(node=>node.children[0]===text);
const render=view=>{current=view;cursor=0;return plugin.content.type();};
const setup=view=>{view.cleanups=view.effects.map(effect=>effect()).filter(Boolean);};
const unmount=view=>{for(const cleanup of view.cleanups)cleanup();};
const mount=()=>{const view={hooks:[],effects:[],cleanups:[],updates:0};view.tree=render(view);setup(view);return view;};
const reply=(call,error,result)=>listeners.find(listener=>listener.type==='message').handler({source:parent,
  data:{type:'framey:reply',id:call.id,error,result}});
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const toastCount=()=>elements.get('framey-toasts').children.length;

// Leaving before the initial read completes must retire its UI and callbacks.
let view=mount(),read=calls.at(-1);assert.equal(read.method,'get_setting');
const staleToggle=toggle(view.tree).props.onChange;
const staleReload=button(view.tree,'Reload saved setting').props.onClick;
const staleReset=button(view.tree,'Reset example setting').props.onClick;
unmount(view);let updates=view.updates;reply(read,undefined,true);await tick();
assert.equal(view.updates,updates,'late read must not update a retired settings view');
let count=calls.length;staleToggle(false);staleReload();staleReset();await tick();
assert.equal(calls.length,count,'retained handlers must not issue requests after unmount');

// A write already sent may finish, but its retired view must stay silent.
for(const failure of [undefined,'Synthetic retired save failure']) {
  view=mount();reply(calls.at(-1),undefined,true);await tick();view.tree=render(view);
  toggle(view.tree).props.onChange(false);const write=calls.at(-1);assert.equal(write.method,'set_setting');
  unmount(view);updates=view.updates;const toasts=toastCount();
  reply(write,failure,true);await tick();
  assert.equal(view.updates,updates,'late write must not update retired UI');
  assert.equal(toastCount(),toasts,'late write must not announce a retired save');
}

// A reset dialog belongs to its settings view; retiring it closes without saving.
view=mount();reply(calls.at(-1),undefined,true);await tick();view.tree=render(view);
button(view.tree,'Reset example setting').props.onClick();
const modal=roots.get(elements.get('framey-modal'));assert.equal(modal.tree.length,1);
const staleOK=modal.tree[0].children[1].props.onOK;count=calls.length;
unmount(view);await tick();assert.equal(modal.tree,null,'retired settings must close their reset dialog');
await staleOK();assert.equal(calls.length,count,'retired Reset must not save');

// React development mode replays setup/cleanup using the same component refs.
// The first read cannot settle or unlock the fresh read started by that replay.
view=mount();const firstRead=calls.at(-1);unmount(view);setup(view);
const freshRead=calls.at(-1);assert.notEqual(freshRead.id,firstRead.id,'effect replay must start a fresh read');
updates=view.updates;reply(firstRead,undefined,true);await tick();assert.equal(view.updates,updates);
view.tree=render(view);assert.equal(toggle(view.tree).props.disabled,true);
count=calls.length;toggle(view.tree).props.onChange(false);assert.equal(calls.length,count);
reply(freshRead,undefined,false);await tick();view.tree=render(view);
assert.equal(toggle(view.tree).props.checked,false);assert.equal(toggle(view.tree).props.disabled,false);
toggle(view.tree).props.onChange(true);assert.equal(calls.length,count+1);
assert.equal(calls.at(-1).method,'set_setting');reply(calls.at(-1),undefined,true);await tick();
unmount(view);
