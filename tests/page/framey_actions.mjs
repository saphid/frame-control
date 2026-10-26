import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8');
const testSource=source.replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n  window.__surface=PluginSurface; window.__legacy=legacyServerAPI;\n})();');
assert.notEqual(testSource,source);
const states=[];
const React={Fragment:'fragment',Component:class {},createElement:(type,props,...children)=>({type,props:props||{},children}),
  useState:value=>[value,next=>states.push(next)], useEffect(){},isValidElement:value=>!!value?.type};
class Element {constructor(){this.children=[];this.textContent='';this.attributes={};}
  append(...children){this.children.push(...children);}setAttribute(key,value){this.attributes[key]=value;}
  remove(){this.removed=true;}}
const elements=new Map();
const roots=new Map();
const window={React,ReactDOM:{createRoot:node=>{
  const root={render(value){this.value=value;},unmount(){this.unmounted=true;}};
  roots.set(node,root);return root;
}},addEventListener(){}};
const listeners=[];const messages=[];const parent={postMessage:message=>messages.push(message)};
const context=vm.createContext({window,document:{getElementById:id=>{
  if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},createElement:()=>new Element()},
  navigator:{language:'en'}, parent,DOMException,addEventListener:(type,handler)=>listeners.push({type,handler}),
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
// Disabled controls stay inert even if a caller invokes their handlers directly.
let changed=0;
const toggle=nodes(window.DFL.ToggleField({label:'Enabled',checked:true,disabled:true,
  onChange:()=>changed++}),'input')[0];
const options=[{label:'Modes',options:[{label:'Slow',data:'slow'},{label:'Fast',data:'fast'}]}];
const dropdown=nodes(window.DFL.Dropdown({rgOptions:options,selectedOption:'fast',disabled:true,
  onChange:()=>changed++}),'select')[0];
const button=nodes(window.DFL.ButtonItem({label:'Reload',description:'Read setting',disabled:true,
  onClick:()=>changed++}),'button')[0];
const input=nodes(window.DFL.TextField({label:'Alias',value:'Old',placeholder:'New',disabled:true,
  onChange:()=>changed++}),'input')[0];
const slider=nodes(window.DFL.SliderField({label:'Speed',value:2,min:0,max:10,step:2,disabled:true,
  onChange:()=>changed++}),'input')[0];
const checkbox=nodes(window.DFL.DialogCheckbox({label:'Game',disabled:true,
  onChange:()=>changed++}),'input')[0];
for(const control of [toggle,dropdown,button,input,slider,checkbox])assert.equal(control.props.disabled,true);
assert.equal(input.props.value,'Old');
assert.equal(slider.props.type,'range');
assert.equal(dropdown.props.value,'1');
assert.equal(nodes(dropdown,'optgroup').length,1);
toggle.props.onChange({target:{checked:false}});
dropdown.props.onChange({target:{value:'0'}});
button.props.onClick({});
input.props.onChange({target:{value:'New'}});
slider.props.onChange({target:{value:'4'}});
checkbox.props.onChange({target:{checked:true}});
assert.equal(changed,0);
let entered='';
const readyInput=nodes(window.DFL.TextField({label:'Alias',value:'Old',onChange:e=>{entered=e.target.value;}}),'input')[0];
readyInput.props.onChange({target:{value:'New'}});assert.equal(entered,'New');
let speed=0;
const readySlider=nodes(window.DFL.SliderField({label:'Speed',value:2,onChange:v=>{speed=v;}}),'input')[0];
readySlider.props.onChange({target:{value:'4'}});assert.equal(speed,4);
let selected;
const readyDropdown=nodes(window.DFL.Dropdown({rgOptions:options,selectedOption:'fast',
  onChange:option=>{selected=option;}}),'select')[0];
readyDropdown.props.onChange({target:{value:'0'}});assert.equal(selected.data,'slow');
const readyButton=nodes(window.DFL.ButtonItem({label:'Reload',onClick:()=>changed++}),'button')[0];
assert.equal(readyButton.props.disabled,false);
readyButton.props.onClick({});assert.equal(changed,1);
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
const call=messages.find(message=>message.type==='framey:call');
assert.equal(call.method,'get_setting');
assert.deepEqual(Array.from(call.args),['mode','default']);
listeners.find(x=>x.type==='message').handler({source:parent,data:{type:'framey:reply',id:call.id,result:'dark'}});
assert.equal(await reply,'dark');
await assert.rejects(api.call('x;alert(1)'),/Invalid backend method/);

const toast=api.toaster.toast({title:'Saved',body:'Mode updated',duration:4000});
const toastNode=elements.get('framey-toasts').children[0];
assert.equal(toastNode.attributes.role,'status');
assert.equal(toastNode.children[0].textContent,'Saved');
assert.equal(toastNode.children[1].textContent,'Mode updated');
toast.dismiss();assert.equal(toastNode.removed,true);
// Decky's toast fields are ReactNode values. Keep JSX in the panel instead of
// showing "[object Object]", and release their React roots on dismissal.
const heading=React.createElement('em',null,'Saved');
const detail=React.createElement('span',null,'Mode updated');
const icon=React.createElement('svg',null);
const rich=api.toaster.toast({title:heading,body:[detail,' again'],icon,
  subtext:'Open settings',showToast:true});
const richNode=elements.get('framey-toasts').children[1];
assert.equal(roots.get(richNode.children[0]).value,icon);
assert.equal(roots.get(richNode.children[1]).value,heading);
assert.deepEqual(Array.from(roots.get(richNode.children[2]).value),[detail,' again']);
assert.equal(richNode.children[3].textContent,'Open settings');
rich.dismiss();rich.dismiss();
assert.equal(richNode.removed,true);
for(const node of richNode.children.slice(0,3))assert.equal(roots.get(node).unmounted,true);
let opened=0;
const actionable=api.toaster.toast({title:'Open',onClick:()=>opened++});
const actionNode=elements.get('framey-toasts').children[2];
actionNode.children.at(-1).onclick();
assert.equal(opened,1);
assert.equal(actionNode.removed,true);
actionable.dismiss();
const hidden=api.toaster.toast({title:heading,showToast:false});
assert.equal(elements.get('framey-toasts').children.length,3);
hidden.dismiss();

function LocalRoute(){return React.createElement('p',null,'Route content');}
const undo=api.routerHook.addRoute('/plugin/details',LocalRoute);
assert.equal(window.DFL.Navigation.Navigate('/plugin/details'),true);
assert.equal(nodes(window.__surface({plugin}),LocalRoute).length,1);
assert.equal(window.DFL.Navigation.Navigate('/decky/store'),false);
assert.equal(window.DFL.findModuleChild(()=>true),null);
window.DFL.Navigation.CloseSideMenus();
assert.equal(nodes(window.__surface({plugin}),LocalRoute).length,0);
undo();assert.equal(window.DFL.Navigation.Navigate('/plugin/details'),false);

// Legacy backend methods preserve Decky keyword arguments and success envelopes.
const legacyReply=window.__legacy.callPluginMethod('get_setting',{key:'theme'});
const legacyCall=messages.filter(message=>message.type==='framey:call').at(-1);
assert.equal(legacyCall.legacy,true);
assert.deepEqual(JSON.parse(JSON.stringify(legacyCall.args)),[{key:'theme'}]);
listeners.find(x=>x.type==='message').handler({source:parent,data:{type:'framey:reply',id:legacyCall.id,
  result:{success:true,result:'dark'}}});
assert.equal((await legacyReply).result,'dark');
assert.equal((await window.__legacy.callPluginMethod('get_setting',[])).success,false);
const failedLegacy=window.__legacy.callPluginMethod('get_setting',{});
const failedCall=messages.filter(message=>message.type==='framey:call').at(-1);
listeners.find(x=>x.type==='message').handler({source:parent,data:{type:'framey:reply',id:failedCall.id,error:'Unavailable'}});
assert.equal((await failedLegacy).success,false);

// Local UI controls work without Steam components or fabricated hardware data.
const tabChanges=[];
const tabs=window.DFL.Tabs({tabs:[{id:'one',title:'One',content:'First'},
  {id:'two',title:'Two',content:'Second'},{id:'locked',title:'Locked',disabled:true}],
  activeTab:'two',onShowTab:id=>tabChanges.push(id)});
assert.equal(nodes(tabs,'button')[1].props['aria-selected'],true);
assert.deepEqual(nodes(tabs,'div').at(-1).children,['Second']);
nodes(tabs,'button')[0].props.onClick();
nodes(tabs,'button')[2].props.onClick();
assert.deepEqual(tabChanges,['one']);
assert.equal(window.DFL.Spinner({}).props.role,'status');
assert.equal(window.DFL.ProgressBar({nProgress:120}).props.value,100);
assert.equal(window.DFL.joinClassNames('one',null,'two'),'one two');
let eventCount=0;
const unsubscribe=window.SteamClient.GameSessions.RegisterForAppLifetimeNotifications(()=>eventCount++);
assert.equal(typeof unsubscribe,'function');
assert.equal(unsubscribe.unregister,unsubscribe);
unsubscribe.unregister();unsubscribe();assert.equal(eventCount,0);
assert.equal(window.SteamClient.System.ShutdownPC,undefined);
assert.equal(window.DFL.Router.MainRunningApp,undefined);
assert.equal(window.DFL.Router.RunningApps.length,0);
assert.equal(window.DFL.Router.RunningApps,window.SteamUIStore.RunningApps);
assert.ok(Object.isFrozen(window.SteamUIStore));
assert.ok(Object.isFrozen(window.SuspendResumeStore));
assert.equal(window.SuspendResumeStore.InitiateSleep,undefined);
for(const name of ['App','appStore','appInfoStore','collectionStore'])assert.equal(window[name],undefined);
for(const register of [window.SteamClient.System.UI.RegisterForSystemKeyEvents,
  window.SteamClient.Apps.RegisterForGameActionUserRequest]){
  const dispose=register(()=>eventCount++);assert.equal(dispose.unregister,dispose);dispose();
}
assert.equal(eventCount,0);
const image=window.DFL.SuspensefulImage({src:'data:image/svg+xml,<svg/>',alt:'Setup',style:{width:50}});
assert.equal(image.type,'img');assert.equal(image.props.alt,'Setup');assert.equal(image.props.style.width,50);
await assert.rejects(window.SteamClient.Storage.GetJSON('missing'),/Not found/);
await window.SteamClient.Storage.SetObject('settings',{enabled:false,count:3});
assert.equal(await window.SteamClient.Storage.GetJSON('settings'),'{"enabled":false,"count":3}');
assert.equal(window.localStorage.getItem('steam-client:settings'),'{"enabled":false,"count":3}');
await assert.rejects(window.SteamClient.Storage.SetObject('large','x'.repeat(65537)),/Framey plugin cache is full/);
await assert.rejects(window.SteamClient.Storage.SetObject('undefined',undefined),/JSON value/);
assert.equal(window.indexedDB,undefined); // localForage must use bounded plugin storage.
const unpatch=window.DFL.beforePatch({},'method',()=>{});
assert.equal(unpatch.unpatch,unpatch);unpatch.unpatch();
assert.equal(typeof window.DFL.showModal({type:'p'}).Close,'function');
let selectedMenuItem=0;
window.DFL.MenuItem({onSelected:()=>selectedMenuItem++}).props.onClick({});
window.DFL.MenuItem({disabled:true,onSelected:()=>selectedMenuItem++}).props.onClick({});
window.DFL.MenuItem({bDisabled:true,onSelected:()=>selectedMenuItem++}).props.onClick({});
window.DFL.MenuItem({onClick:()=>selectedMenuItem++,onSelected:()=>selectedMenuItem++}).props.onClick({});
assert.equal(selectedMenuItem,2);
for (const [locale,expected] of [['de-DE','german'],['zh-CN','schinese'],['zh-TW','tchinese'],
  ['pt-BR','brazilian'],['en-US','english'],['xx-ZZ','english']]) {
  context.navigator.language=locale;
  assert.equal(await window.SteamClient.Settings.GetCurrentLanguage(),expected);
}
function GameRoute(){return React.createElement('p',null,window.DFL.useParams().appid);}
const removeGame=api.routerHook.addRoute('/plugin/game/:appid/:view?',GameRoute);
assert.equal(window.DFL.Navigation.Navigate('/plugin/game/123'),true);
assert.equal(window.DFL.useParams().appid,'123');
assert.equal(window.DFL.useParams().view,undefined);
assert.equal(nodes(window.__surface({plugin}),GameRoute).length,1);
assert.equal(window.DFL.Navigation.Navigate('/plugin/game/123/art'),true);
assert.equal(window.DFL.useParams().view,'art');
assert.equal(window.DFL.Navigation.Navigate('/plugin/game/123/art/extra'),false);
assert.equal(window.DFL.Navigation.Navigate('/plugin/game/123?admin=1'),false);
assert.equal(window.DFL.Navigation.Navigate('/plugin/game//art'),false);
assert.throws(()=>api.routerHook.addRoute('/plugin/:id/:id',GameRoute));
assert.throws(()=>api.routerHook.addRoute('/plugin/:id?/art',GameRoute));
removeGame();
assert.equal(window.DFL.useParams().appid,undefined);
assert.equal(nodes(window.__surface({plugin}),GameRoute).length,0);

// Event subscription is acknowledged before a method that immediately emits.
const onMessage=listeners.find(x=>x.type==='message').handler;
const eventValues=[];
const callback=(...args)=>eventValues.push(args);
assert.equal(api.addEventListener('timer:tick',callback),callback);
const subscribe=messages.at(-1);
assert.equal(subscribe.type,'framey:events');
assert.deepEqual(Array.from(subscribe.args[0]),['timer:tick']);
const before=messages.length;
const timerCall=api.call('load_remaining_seconds');
assert.equal(messages.length,before);
// Other windows cannot inject backend replies.
onMessage({source:{},data:{type:'framey:reply',id:subscribe.id,result:{events:[],cursor:0}}});
await Promise.resolve();assert.equal(messages.length,before);
onMessage({source:parent,data:{type:'framey:reply',id:subscribe.id,
  result:{events:[{event:'timer:tick',args:[12,'seconds']}],cursor:1}}});
for(let i=0;i<12;i++)await Promise.resolve();
assert.deepEqual(eventValues,[[12,'seconds']]);
const timerRequest=messages.at(-1);
assert.equal(timerRequest.type,'framey:call');assert.equal(timerRequest.method,'load_remaining_seconds');
onMessage({source:parent,data:{type:'framey:reply',id:timerRequest.id,result:null}});await timerCall;
api.removeEventListener('timer:tick',callback);
const unsubscribeRequest=messages.at(-1);assert.equal(unsubscribeRequest.type,'framey:events');
assert.equal(unsubscribeRequest.args[0].length,0);
onMessage({source:parent,data:{type:'framey:reply',id:unsubscribeRequest.id,
  result:{events:[{event:'timer:tick',args:[99]}],cursor:2}}});
for(let i=0;i<12;i++)await Promise.resolve();assert.equal(eventValues.length,1);
assert.throws(()=>api.addEventListener('bad event',callback),/Invalid Decky event/);
assert.throws(()=>api.addEventListener('tick',null),/Invalid Decky event/);
listeners.find(x=>x.type==='unload').handler();
assert.equal(messages.at(-1).type,'framey:events:close');
