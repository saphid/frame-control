// Exact published TabMaster list; no initializer, backend or Steam mutation.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8');
const host=source.replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n})();');
assert.notEqual(host,source);
let slots=[],cursor=0,updates=0;const effects=[],cleanups=[];
const React={Fragment:'fragment',Component:class {},forwardRef:render=>render,createElement:(type,props,...children)=>({type,props:props||{},children}),
  useState:initial=>{const index=cursor++;if(!(index in slots))slots[index]=typeof initial==='function'?initial():initial;
    return [slots[index],value=>{updates++;slots[index]=typeof value==='function'?value(slots[index]):value;}];},
  useRef:initial=>{const index=cursor++;return slots[index]??={current:initial};},
  useEffect:(effect,deps)=>{const index=cursor++;
    if(!slots[index]||deps.some((value,i)=>value!==slots[index][i])){slots[index]=deps;effects.push(effect);}}};
const window={React,ReactDOM:{createRoot:()=>({render(){}})}};
const context=vm.createContext({window,navigator:{language:'en'},document:{getElementById:()=>({})},
  parent:{postMessage:message=>assert.equal(message.type,'framey:cache:init')},
  addEventListener(){},setTimeout:()=>1,clearTimeout(){}});
vm.runInContext(host,context);
const ids=[],original=Object.freeze([
  Object.freeze({label:'Third',position:2,data:{id:'third'}}),
  Object.freeze({label:'First',position:0,data:{id:'first'}}),
  Object.freeze({label:'Second',position:1,data:{id:'second'}}),
]);
const TabEntryInteractables=()=>null;
Object.assign(context,{DFL:window.DFL,entries:original,TabEntryInteractables,
  tabMasterManager:{reorderTabs:order=>ids.push(Array.from(order))}});
const control=vm.runInContext(readFileSync(0,'utf8'),context);
assert.equal(typeof control.type,'function','the published list must resolve to a Framey control');
let props=control.props;
const nodes=(tree,type)=>Array.isArray(tree)?tree.flatMap(child=>nodes(child,type)):
  [...(tree?.type===type?[tree]:[]),...(tree?.children||[]).flatMap(child=>nodes(child,type))];
const render=(next=props)=>{
  props=next;cursor=0;let tree=control.type(props);
  for(const effect of effects.splice(0)){const cleanup=effect();if(cleanup)cleanups.push(cleanup);}
  cursor=0;return control.type(props);
};
const buttons=(tree,text)=>nodes(tree,'button').filter(node=>node.children.includes(text));
const button=(tree,text)=>buttons(tree,text)[0];
const labels=tree=>nodes(tree,'li').map(item=>item.props['aria-label']);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
let tree=render();
assert.deepEqual(labels(tree),['First','Second','Third']);
assert.equal(nodes(tree,TabEntryInteractables).length,3);
assert.equal(nodes(tree,TabEntryInteractables)[0].props.entry.data,original[1].data);
assert.equal(buttons(tree,'Move up')[0].props.disabled,true);
assert.equal(buttons(tree,'Move down')[2].props.disabled,true);
const retainedMove=buttons(tree,'Move down')[0].props.onClick;
retainedMove();retainedMove();tree=render();
assert.deepEqual(labels(tree),['Second','First','Third'],'retained rapid callback must not move twice');
assert.deepEqual(ids,[],'moving must not save');
button(tree,'Cancel reordering').props.onClick();tree=render();
assert.deepEqual(labels(tree),['First','Second','Third']);assert.deepEqual(ids,[]);
buttons(tree,'Move up')[2].props.onClick();tree=render();
assert.deepEqual(labels(tree),['First','Third','Second']);
const retainedSave=button(tree,'Save order').props.onClick;
retainedSave();retainedSave();await tick();tree=render();
assert.deepEqual(ids,[['first','third','second']],'published save callback receives the chosen data order once');
assert.deepEqual(original.map(entry=>entry.position),[2,0,1],'plugin-owned objects must not be mutated');
assert.deepEqual(labels(tree),['First','Third','Second']);

// Async author callbacks stay busy, show rejection and permit an explicit retry.
let saves=0,accept,reject,received;
const asyncSave=entries=>{saves++;received=entries;return new Promise((resolve,fail)=>{accept=resolve;reject=fail;});};
tree=render({...props,onSave:asyncSave});
buttons(tree,'Move down')[0].props.onClick();tree=render();
const save=button(tree,'Save order').props.onClick;save();save();tree=render();
assert.equal(saves,1);assert.equal(button(tree,'Save order').props.disabled,true);
assert.equal(button(tree,'Cancel reordering').props.disabled,true);
assert.ok(buttons(tree,'Move down').every(node=>node.props.disabled));
reject(Error('Synthetic save refused'));await tick();tree=render();
assert.match(nodes(tree,'p').find(node=>node.props.role==='alert').children[0],/Synthetic save refused/);
button(tree,'Save order').props.onClick();assert.equal(saves,2);accept();await tick();tree=render();
assert.deepEqual(Array.from(received,entry=>entry.position),[0,1,2]);
assert.equal(nodes(tree,TabEntryInteractables).length,3);

// A replaced list and disabled state invalidate handlers held before redraw.
const staleMove=buttons(tree,'Move down')[0].props.onClick;
const replacement=[{label:'Replacement',position:0,data:{id:'replacement'}}];
tree=render({...props,entries:replacement});staleMove();tree=render();
assert.deepEqual(labels(tree),['Replacement']);
assert.equal(button(tree,'Move up').props.disabled,true);assert.equal(button(tree,'Move down').props.disabled,true);
tree=render({...props,entries:original});const oldMove=buttons(tree,'Move down')[0].props.onClick;
oldMove();tree=render();const oldSave=button(tree,'Save order').props.onClick;
tree=render({...props,disableReordering:true});oldMove();tree=render();
const beforeDisabledSave=saves;oldSave();assert.equal(saves,beforeDisabledSave);
assert.deepEqual(labels(tree),['First','Second','Third']);
assert.equal(buttons(tree,'Move down').length,0);
assert.equal(buttons(tree,'Save order').length,0);assert.equal(buttons(tree,'Cancel reordering').length,0);
assert.equal(nodes(tree,TabEntryInteractables).length,3,'ordinary entry actions remain available when reordering is disabled');

// Replacing entries during a pending save must ignore its late completion.
tree=render({...props,disableReordering:false});buttons(tree,'Move down')[0].props.onClick();tree=render();
button(tree,'Save order').props.onClick();tree=render({...props,entries:replacement});
reject(Error('Retired save failed'));await tick();tree=render();
assert.deepEqual(labels(tree),['Replacement']);assert.equal(nodes(tree,'p').filter(node=>node.props.role==='alert').length,0);
// Even a rejection without an Error object must leave the draft available.
tree=render({...props,entries:original,onSave:()=>Promise.reject(null)});
buttons(tree,'Move down')[0].props.onClick();tree=render();button(tree,'Save order').props.onClick();
await tick();tree=render();assert.equal(button(tree,'Save order').props.disabled,false);
assert.equal(nodes(tree,'p').find(node=>node.props.role==='alert').children[0],'null');
// Retiring the component also retires its completion updates.
tree=render({...props,onSave:asyncSave});button(tree,'Save order').props.onClick();
for(const cleanup of cleanups)cleanup();
const beforeUnmountCompletion=updates;accept();await tick();
assert.equal(updates,beforeUnmountCompletion,'a late save must not update an unmounted list');
