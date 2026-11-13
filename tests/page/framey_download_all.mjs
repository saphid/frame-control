// Exercise the exact managed official component, including filters and failure UI.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const bundle=readFileSync(process.argv[2],'utf8');
const hooks=[],effects=[],toasts=[],batches=[];let cursor=0,downloadListener,finish,fail;
const element=(type,props)=>({type,props:props||{}});
const context=vm.createContext({console,localStorage:{getItem:()=>null,setItem(){}},
  SP_JSX:{jsx:element,jsxs:element,Fragment:'Fragment'},
  DFL:{ButtonItem:'Button',PanelSection:'Section',PanelSectionRow:'Row',SliderField:'Slider'},
  SP_REACT:{useState(initial){const n=cursor++;if(!(n in hooks))hooks[n]=initial;
    return [hooks[n],value=>hooks[n]=value];},
    useRef(initial){const n=cursor++;return hooks[n]??=( {current:initial} );},
    useEffect(fn){const n=cursor++;if(!(n in hooks)){hooks[n]=true;effects.push(fn);}}},
  SteamClient:{Downloads:{RegisterForDownloadItems(fn){downloadListener=fn;return {unregister(){}};},
    FrameyQueueDownloads:ids=>{batches.push([...ids]);return new Promise((resolve,reject)=>{finish=resolve;fail=reject;});}}},
  window:{__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit:{
    connect:()=>({_version:2,callable:()=>async()=>({success:true}),toaster:{toast:value=>toasts.push(value)}})}}});
vm.runInContext(bundle.replace('export { index as default };','globalThis.component=PluginContent;'),context);
const nodes=(node,type)=>!node?[]:Array.isArray(node)?node.flatMap(child=>nodes(child,type)):
  typeof node==='object'?[...(node.type===type?[node]:[]),...nodes(node.props?.children,type)]:[];
const text=node=>typeof node==='boolean'?'':Array.isArray(node)?node.map(text).join(''):
  typeof node==='object'?text(node?.props?.children):String(node??'');
const render=()=>{cursor=0;const tree=context.component();while(effects.length)effects.shift()();return tree;};
const button=(tree,label)=>nodes(tree,'Button').find(node=>text(node)===label);
assert.equal(button(render(),'Queue 0 Downloads').props.disabled,true);
const row=(appid,size,deferred_time=10,queue_index=-1,completed=false)=>({appid,queue_index,completed,
  deferred_time,update_type_info:[{has_update:true,completed_update:false,progress:[{bytes_total:size}]}]});
downloadListener(true,[{remote_client_id:'0',item_data:[row(1,100),row(2,6*1024**3),
  row(3,5,10,0),row(4,1,10,-1,true),row(5,20,0)]}]);
let tree=render();
assert.equal(button(tree,'Queue 2 Downloads').props.disabled,false);
const pending=button(tree,'Queue 2 Downloads').props.onClick();
assert.deepEqual(batches.at(-1),[1,2]);assert.equal(toasts.length,0,'no success before Steam replies');
fail(Error('Private queue refused'));
await pending;assert.equal(toasts.at(-1).title,'Download queue stopped');
assert.equal(toasts.at(-1).body,'Private queue refused');
button(tree,'All').props.onClick();tree=render();
const all=button(tree,'Queue 3 Downloads').props.onClick();
assert.deepEqual(batches.at(-1),[5,1,2]);
finish({queued:3});await all;assert.equal(toasts.at(-1).title,'Download All');
button(tree,'Scheduled With Size Limit').props.onClick();tree=render();
assert.equal(nodes(tree,'Slider').length,1);
const small=button(tree,'Queue 1 Download').props.onClick();assert.deepEqual(batches.at(-1),[1]);
finish({queued:1});await small;
downloadListener(true,[{remote_client_id:'0',item_data:[]}]);
assert.equal(button(render(),'Queue 0 Downloads').props.disabled,true);
