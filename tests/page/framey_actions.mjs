import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8');
const testSource=source.replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n  window.__surface=PluginSurface;\n})();');
assert.notEqual(testSource,source);
const states=[];
const React={Fragment:'fragment',Component:class {},createElement:(type,props,...children)=>({type,props:props||{},children}),
  useState:value=>[value,next=>states.push(next)], useEffect(){},isValidElement:value=>!!value?.type};
class Element {constructor(){this.children=[];this.textContent='';this.attributes={};}
  append(...children){this.children.push(...children);}setAttribute(key,value){this.attributes[key]=value;}
  remove(){this.removed=true;}}
const elements=new Map();
const window={React,ReactDOM:{createRoot:()=>({render(){}})},addEventListener(){}};
const listeners=[];const messages=[];const parent={postMessage:message=>messages.push(message)};
const context=vm.createContext({window,document:{getElementById:id=>{
  if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},createElement:()=>new Element()},
  navigator:{language:'en'}, parent,addEventListener:(type,handler)=>listeners.push({type,handler}),
  setTimeout:()=>1,clearTimeout(){}});
vm.runInContext(testSource,context);
// Official @decky/rollup bundles use the automatic JSX runtime, including keyed lists.
const jsx=window.SP_JSX.jsx('p',{id:'message',children:'Saved'},'message-key');
assert.equal(jsx.type,'p');
assert.equal(jsx.props.id,'message');
assert.equal(jsx.props.key,'message-key');
assert.deepEqual(jsx.children,['Saved']);
const fragments=window.SP_JSX.jsxs(window.SP_JSX.Fragment,{children:['one','two']});
assert.equal(fragments.type,React.Fragment);
assert.deepEqual(fragments.children,[['one','two']]);
const nodes=(tree,type)=>Array.isArray(tree)?tree.flatMap(child=>nodes(child,type)):
  [...(tree?.type===type?[tree]:[]),...(tree?.children||[]).flatMap(child=>nodes(child,type))];
// Common Decky controls must honor disabled and provide numeric/text inputs.
const toggle=nodes(window.DFL.ToggleField({label:'Enabled',checked:true,disabled:true}),'input')[0];
assert.equal(toggle.props.disabled,true);
const button=nodes(window.DFL.ButtonItem({children:'Refresh',disabled:true}),'button')[0];
assert.equal(button.props.disabled,true);
let entered='';
const input=nodes(window.DFL.TextField({label:'Alias',value:'Old',placeholder:'New',disabled:true,
  onChange:event=>{entered=event.target.value;}}),'input')[0];
assert.equal(input.props.value,'Old');
assert.equal(input.props.disabled,true);
input.props.onChange({target:{value:'New'}});assert.equal(entered,'New');
let speed=0;
const slider=nodes(window.DFL.SliderField({label:'Speed',value:2,min:0,max:10,step:2,disabled:true,
  onChange:value=>{speed=value;}}),'input')[0];
assert.equal(slider.props.type,'range');
assert.equal(slider.props.disabled,true);
slider.props.onChange({target:{value:'4'}});assert.equal(speed,4);
let selected;
const options=[{label:'Modes',options:[{label:'Slow',data:'slow'},{label:'Fast',data:'fast'}]}];
const dropdown=nodes(window.DFL.Dropdown({rgOptions:options,selectedOption:'fast',disabled:true,
  onChange:option=>{selected=option;}}),'select')[0];
assert.equal(dropdown.props.disabled,true);
assert.equal(dropdown.props.value,'1');
assert.equal(nodes(dropdown,'optgroup').length,1);
dropdown.props.onChange({target:{value:'0'}});assert.equal(selected.data,'slow');
let called=0;
const plugin={content:{type:'content'},settings:{type:'settings'},titleView:{type:'title'},
  frameyQuickActions:[{label:'Refresh data',onClick:async()=>{called++;return 'Fresh';}},
    {label:'invalid'},...Array.from({length:9},(_,i)=>({label:`Action ${i}`,onClick:()=>{}}))]};
const tree=window.__surface({plugin});
const buttons=nodes(tree,'button');
assert.equal(buttons.length,9); // Panel, Settings, and seven valid actions inside the first eight entries.
assert.equal(nodes(tree,'nav')[0].props['aria-label'],'Plugin views');
assert.equal(nodes(tree,'section')[0].props['aria-label'],'Plugin quick actions');
assert.equal(nodes(tree,'header').length,1);
await buttons[2].props.onClick();
assert.equal(called,1);
assert.deepEqual(states.slice(-3),[0,'Refresh data…','Fresh',null].slice(-3));
assert.equal(nodes(window.__surface({plugin:{settings:{type:'settings'}}}),'nav').length,1);

// API v2 backend calls remain request-scoped and errors return to the caller.
const api=window.__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit.connect(2,'Test');
const reply=api.call('get_setting','mode','default');
assert.equal(messages[0].method,'get_setting');
assert.deepEqual(Array.from(messages[0].args),['mode','default']);
listeners.find(x=>x.type==='message').handler({source:parent,data:{type:'framey:reply',id:messages[0].id,result:'dark'}});
assert.equal(await reply,'dark');
await assert.rejects(api.call('x;alert(1)'),/Invalid backend method/);

const toast=api.toaster.toast({title:'Saved',body:'Mode updated',duration:4000});
const toastNode=elements.get('framey-toasts').children[0];
assert.equal(toastNode.attributes.role,'status');
assert.equal(toastNode.children[0].textContent,'Saved');
assert.equal(toastNode.children[1].textContent,'Mode updated');
toast.dismiss();assert.equal(toastNode.removed,true);

function LocalRoute(){return React.createElement('p',null,'Route content');}
const undo=api.routerHook.addRoute('/plugin/details',LocalRoute);
assert.equal(window.DFL.Navigation.Navigate('/plugin/details'),true);
assert.equal(nodes(window.__surface({plugin}),LocalRoute).length,1);
assert.equal(window.DFL.Navigation.Navigate('/decky/store'),false);
undo();assert.equal(window.DFL.Navigation.Navigate('/plugin/details'),false);
