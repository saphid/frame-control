import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const host=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8')
  .replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n})();');
const bundle=readFileSync(new URL('../../examples/framey-settings/dist/index.js',import.meta.url),'utf8');
assert.match(bundle,/SP_JSX\.jsx/);
const React={Fragment:Symbol('fragment'),Component:class {},
  createElement:(type,props,...children)=>({type,props:props||{},children}),
  useState:value=>[value,()=>{}],useEffect(){},isValidElement:value=>!!value?.type};
class Element {
  constructor(){this.children=[];this.textContent='';this.attributes={};}
  append(...nodes){this.children.push(...nodes);}
  setAttribute(name,value){this.attributes[name]=value;}
  remove(){this.removed=true;}
}
const elements=new Map(), roots=new Map();
const document={getElementById:id=>{
  if(!elements.has(id))elements.set(id,new Element());return elements.get(id);
},createElement:()=>new Element()};
const window={React,ReactDOM:{createRoot:node=>{
  const root={render(value){this.value=value;},unmount(){this.unmounted=true;}};
  roots.set(node,root);return root;
}},addEventListener(){}};
const listeners=[];
const calls=[];
const parent={postMessage(message){
  if(message.type!=='framey:call')return;
  calls.push(message);
  listeners.find(x=>x.type==='message').handler({source:parent,
    data:{type:'framey:reply',id:message.id,result:true}});
}};
const context=vm.createContext({window,document,
  navigator:{language:'en'},parent,addEventListener:(type,handler)=>listeners.push({type,handler}),
  setTimeout:()=>1,clearTimeout(){}});
vm.runInContext(host,context);
Object.assign(context,{SP_REACT:window.SP_REACT,SP_JSX:window.SP_JSX,DFL:window.DFL});
vm.runInContext(bundle.replace(/export \{ index as default \};/, 'window.sample = index;'),context);
const plugin=window.sample();
assert.equal(plugin.name,'Framey Settings Sample');
assert.equal(typeof plugin.content.type,'function');
const content=plugin.content.type();
assert.equal(content.type,window.DFL.PanelSection);
assert.equal(content.props.title,'Framey settings sample');
assert.equal(content.children[0][0].type,window.DFL.PanelSectionRow);
assert.equal(plugin.settings.type,plugin.content.type);
assert.equal(plugin.frameyQuickActions[0].label,'Read saved setting');
assert.equal(await plugin.frameyQuickActions[0].onClick(),'Saved setting is on');
assert.equal(calls[0].method,'get_setting');
assert.deepEqual(Array.from(calls[0].args),['enabled',false]);
// Exercise the built sample's save path through the real Framey toast host.
// Its JSX body must reach a React root, rather than stringify to an object.
content.children[0][0].children[0].props.onChange(true);
await new Promise(resolve=>setImmediate(resolve));
const toast=elements.get('framey-toasts').children[0];
assert.equal(toast.attributes.role,'status');
assert.equal(toast.children[0].textContent,'Framey sample');
const toastBody=roots.get(toast.children[1]).value;
assert.equal(toastBody.type,'span');
assert.match(JSON.stringify(toastBody),/Setting saved/);
assert.match(JSON.stringify(toastBody),/on/);
toast.children[2].onclick();
assert.equal(roots.get(toast.children[1]).unmounted,true);
assert.equal(window.DFL.Navigation.Navigate('/framey-sample/details/saved-setting'),true);
assert.equal(window.DFL.useParams().topic,'saved-setting');
assert.equal(window.DFL.Navigation.Navigate('/library/home'),false);
plugin.onDismount();
assert.equal(window.DFL.useParams().topic,undefined);
assert.equal(window.DFL.Navigation.Navigate('/framey-sample/details/saved-setting'),false);
