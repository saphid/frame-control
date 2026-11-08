import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const host=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8')
  .replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n})();');
const bundle=readFileSync(new URL('../../examples/framey-settings/dist/index.js',import.meta.url),'utf8');
assert.match(bundle,/SP_JSX\.jsx/);
const states=[];
const React={Fragment:Symbol('fragment'),Component:class {},
  createElement:(type,props,...children)=>({type,props:props||{},children}),
  cloneElement:(element,props)=>({...element,props:{...element.props,...props}}),
  useState:value=>[value,next=>states.push(next)],useRef:value=>({current:value}),
  useEffect(){},isValidElement:value=>!!value?.type};
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
const window={React,location:{hash:'#sample-session'},ReactDOM:{createRoot:node=>{
  const root={render(value){this.value=value;},unmount(){this.unmounted=true;}};
  roots.set(node,root);return root;
}},addEventListener(){}};
const listeners=[];
const calls=[];
const messages=[];
let deferWrites=false;
const reply=(call,error)=>listeners.find(x=>x.type==='message').handler({source:parent,
  data:{type:'framey:reply',id:call.id,...(error?{error}:{result:true})}});
const parent={postMessage(message){
  messages.push(message);
  if(message.type!=='framey:call')return;
  calls.push(message);
  if(message.method==='set_setting' && deferWrites)return;
  reply(message);
}};
const context=vm.createContext({window,document,
  navigator:{language:'en'},parent,addEventListener:(type,handler)=>listeners.push({type,handler}),
  setTimeout:()=>1,clearTimeout(){}});
vm.runInContext(host,context);
const pointerup=listeners.find(listener=>listener.type==='pointerup').handler;
pointerup({isTrusted:false});
assert.equal(messages.some(message=>message.type==='framey:input'),false);
pointerup({isTrusted:true});
assert.equal(messages.at(-1).type,'framey:input');
assert.equal(messages.at(-1).session,'sample-session');
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
// This lightweight host fixture does not run effects. Complete the sample's
// explicit Reload before exercising writes, just as its mount read would.
content.children[0][1].children[0].props.onClick();
await new Promise(resolve=>setImmediate(resolve));
assert.equal(calls.at(-1).method,'get_setting');
// Exercise the built sample's save path through the real Framey toast host.
// Its JSX body must reach a React root, rather than stringify to an object.
const toggle=content.children[0][0].children[0];
toggle.props.onChange(true);
toggle.props.onChange(false); // Before React redraws disabled, do not race the first write.
await new Promise(resolve=>setImmediate(resolve));
assert.equal(calls.filter(call=>call.method==='set_setting').length,1);
assert.deepEqual(Array.from(calls.find(call=>call.method==='set_setting').args),['enabled',true]);
const toast=elements.get('framey-toasts').children[0];
assert.equal(toast.attributes.role,'status');
assert.equal(toast.children[0].textContent,'Framey sample');
const toastBody=roots.get(toast.children[1]).value;
assert.equal(toastBody.type,'span');
assert.match(JSON.stringify(toastBody),/Setting saved/);
assert.match(JSON.stringify(toastBody),/on/);
toast.children[2].onclick();
assert.equal(roots.get(toast.children[1]).unmounted,true);
toggle.props.onChange(false);
await new Promise(resolve=>setImmediate(resolve));
assert.equal(calls.filter(call=>call.method==='set_setting').length,2,
  'a completed save must release the sample setting lock');
// The sample reset is a real Framey modal: Cancel cannot write, OK writes the
// sample setting only after explicit confirmation.
const reset=content.children[0][2].children[0];
const setCalls=()=>calls.filter(call=>call.method==='set_setting');
const dialog=()=>roots.get(elements.get('framey-modal')).value[0].children[1];
reset.props.onClick();
reset.props.onClick();
assert.equal(roots.get(elements.get('framey-modal')).value.length,1,
  'a rapid second tap must not stack reset dialogs');
assert.equal(dialog().props.strTitle,'Reset example setting?');
let rendered=dialog().type(dialog().props);
rendered.children.find(child=>child?.children?.[0]==='Keep setting').props.onClick();
await new Promise(resolve=>setImmediate(resolve));
assert.equal(setCalls().length,2,'cancel leaves the saved value untouched');
assert.equal(roots.get(elements.get('framey-modal')).value,null);
reset.props.onClick();
rendered=dialog().type(dialog().props);
deferWrites=true;
const resetButton=rendered.children.find(child=>child?.children?.[0]==='Reset');
const pendingReset=resetButton.props.onClick();
assert.equal(setCalls().length,3);
assert.deepEqual(Array.from(setCalls().at(-1).args),['enabled',false]);
assert.notEqual(roots.get(elements.get('framey-modal')).value,null,
  'keep confirmation open until its backend save settles');
assert.equal(roots.get(elements.get('framey-modal')).value[0].children[0].props.disabled,true);
resetButton.props.onClick();
rendered.children.find(child=>child?.children?.[0]==='Keep setting').props.onClick();
roots.get(elements.get('framey-modal')).value[0].children[0].props.onClick();
assert.equal(setCalls().length,3,'pending reset cannot be repeated or cancelled');
const toastCount=elements.get('framey-toasts').children.length;
reply(setCalls().at(-1),'storage unavailable');
await pendingReset;
assert.notEqual(roots.get(elements.get('framey-modal')).value,null,'failed save keeps confirmation open');
assert.equal(roots.get(elements.get('framey-modal')).value[0].children[0].props.disabled,false);
assert.ok(states.some(value=>typeof value==='string' && value.includes('storage unavailable') && value.includes('Reload saved setting')),
  'show the failed save and recovery instructions in the modal');
assert.ok(states.some(value=>typeof value==='string' && value.includes('Could not confirm saved setting:')));
assert.equal(elements.get('framey-toasts').children.length,toastCount,'failed save cannot announce success');
const retriedReset=resetButton.props.onClick();
await retriedReset;
assert.equal(setCalls().length,3,'a failed reset cannot write again before reconciliation');
assert.notEqual(roots.get(elements.get('framey-modal')).value,null,'a blocked retry cannot close as a success');
assert.equal(elements.get('framey-toasts').children.length,toastCount);
rendered.children.find(child=>child?.children?.[0]==='Keep setting').props.onClick();
await new Promise(resolve=>setImmediate(resolve));
assert.equal(roots.get(elements.get('framey-modal')).value,null);
content.children[0][1].children[0].props.onClick();
await new Promise(resolve=>setImmediate(resolve));
assert.equal(calls.at(-1).method,'get_setting');
reset.props.onClick();
rendered=dialog().type(dialog().props);
const recoveredReset=rendered.children.find(child=>child?.children?.[0]==='Reset').props.onClick();
assert.equal(setCalls().length,4,'a successful reload permits a new confirmed save');
assert.deepEqual(Array.from(setCalls().at(-1).args),['enabled',false]);
reply(setCalls().at(-1));
await recoveredReset;
assert.equal(roots.get(elements.get('framey-modal')).value,null);
assert.equal(elements.get('framey-toasts').children.length,toastCount+1,'successful retry may announce the saved value');
// A regular toggle still handles its rejected promise in the panel status.
toggle.props.onChange(true);
reply(setCalls().at(-1),'toggle save failed');
await new Promise(resolve=>setImmediate(resolve));
assert.ok(states.some(value=>typeof value==='string' && value.includes('toggle save failed')));
deferWrites=false;
assert.equal(window.DFL.Navigation.Navigate('/framey-sample/details/saved-setting'),true);
assert.equal(window.DFL.useParams().topic,'saved-setting');
assert.equal(window.DFL.Navigation.Navigate('/library/home'),false);
plugin.onDismount();
assert.equal(window.DFL.useParams().topic,undefined);
assert.equal(window.DFL.Navigation.Navigate('/framey-sample/details/saved-setting'),false);
