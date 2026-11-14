import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8');
const host=source.replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n})();');
assert.notEqual(host,source);
let hooks=[],cursor=0;
const React={Fragment:'fragment',Component:class {},forwardRef:render=>render,
  createElement:(type,props,...children)=>({type,props:props||{},children}),
  cloneElement:(element,props)=>({...element,props:{...element.props,...props}}),
  isValidElement:element=>!!element?.type,
  useState:value=>{const index=cursor++;if(!(index in hooks))hooks[index]=value;
    const state=hooks;return [state[index],value=>{state[index]=value;}];},
  useRef:value=>{const index=cursor++;return hooks[index]??=( {current:value} );},useEffect(){},useImperativeHandle(){}};
const elements=new Map(),roots=new Map();
const window={React,ReactDOM:{createRoot:node=>{
  const root={render:tree=>{root.tree=tree;}};roots.set(node,root);return root;
}}};
const listeners=[];
const context=vm.createContext({window,document:{getElementById:id=>{
  if(!elements.has(id))elements.set(id,{});return elements.get(id);}},
  navigator:{language:'en'},parent:{postMessage:message=>assert.equal(message.type,'framey:cache:init')},
  addEventListener:(type,handler)=>listeners.push({type,handler}),setTimeout(){},clearTimeout(){}});
vm.runInContext(host,context);
const render=(element,state=[])=>{hooks=state;cursor=0;return element.type({...element.props,children:element.children});};
const nodes=(tree,type)=>Array.isArray(tree)?tree.flatMap(child=>nodes(child,type)):
  [...(tree?.type===type?[tree]:[]),...(tree?.children||[]).flatMap(child=>nodes(child,type))];
Object.assign(context,{React,deckyFrontendLib:window.DFL});
// Only this exact published component is evaluated; its useEffect deliberately
// does not run. No radio lookup/playback, keyboard API or backend is invoked.
vm.runInContext(readFileSync(0,'utf8')+'\nwindow.publishedModal=TextFieldModal;',context);
const submitted=[];
const handle=window.DFL.showModal(React.createElement(window.publishedModal,{
  onClosed:text=>submitted.push(text),label:'Search',placeholder:'Station name'}));
const modalRoot=roots.get(elements.get('framey-modal'));
const published=()=>modalRoot.tree.at(-1).children.at(-1).children[0];
const state=[];
let modal=render(published(),state);
const text=nodes(modal,window.DFL.TextField)[0];
nodes(render(text),'input')[0].props.onChange({target:{value:'Synthetic station query'}});
modal=render(published(),state);
let tree=render(modal);
const submit=nodes(tree,'button').find(button=>button.children[0]==='OK');
assert.ok(submit,'published ModalRoot.onOK must have a usable submit action');
assert.equal(submit.props.type,'button');
submit.props.onClick({});
await handle.ClosedPromise;
assert.deepEqual(submitted,['Synthetic station query']);
assert.equal(modalRoot.tree,null,'published callback closes its own modal');
submit.props.onClick({});
assert.deepEqual(submitted,['Synthetic station query'],'a retained action cannot resubmit a closed published dialog');
// Closing the same published dialog must not submit an empty search.
const cancelled=window.DFL.showModal(React.createElement(window.publishedModal,{
  onClosed:text=>submitted.push(text),label:'Search'}));
nodes(modalRoot.tree[0],'button')[0].props.onClick();
await cancelled.ClosedPromise;
assert.deepEqual(submitted,['Synthetic station query']);
// Disabled and display-only roots cannot accidentally invoke an action.
let attempts=0;
tree=render(React.createElement(window.DFL.ModalRoot,{bOKDisabled:true,onOK:()=>attempts++}));
assert.equal(nodes(tree,'button')[0].props.disabled,true);
nodes(tree,'button')[0].props.onClick({});assert.equal(attempts,0);
assert.equal(nodes(render(React.createElement(window.DFL.ModalRoot,{},'Read only')),'button').length,0);
// A pending promise suppresses rapid repeats and outer Close/Escape. A failed
// callback stays visible for retry; the callback owns successful dismissal.
let settle;
const asyncHandle=window.DFL.showModal(React.createElement(window.DFL.ModalRoot,{
  onOK:()=>{attempts++;return new Promise((resolve,reject)=>{settle={resolve,reject};});}}));
const asyncState=[];const asyncElement=published();
tree=render(asyncElement,asyncState);
const action=nodes(tree,'button')[0].props.onClick;
const pending=action({});action({});assert.equal(attempts,1);
assert.equal(nodes(modalRoot.tree[0],'button')[0].props.disabled,true);
nodes(modalRoot.tree[0],'button')[0].props.onClick();
listeners.find(listener=>listener.type==='keydown').handler({key:'Escape',preventDefault(){}});
assert.equal(modalRoot.tree.length,1);
settle.reject(Error('Synthetic submit failed'));await pending;
tree=render(asyncElement,asyncState);
assert.equal(nodes(tree,'p').find(node=>node.props.role==='alert').children[0],'Synthetic submit failed');
assert.equal(nodes(modalRoot.tree[0],'button')[0].props.disabled,false);
const retry=nodes(tree,'button')[0].props.onClick({});assert.equal(attempts,2);
settle.resolve();await retry;
assert.equal(modalRoot.tree.length,1,'ModalRoot does not implicitly dismiss after onOK');
asyncHandle.Close();await asyncHandle.ClosedPromise;
// A callback that opens a child dialog must lock its own parent, leaving the
// child dismissible. Do not accidentally lock whichever dialog is on top.
let child,finish;
const parentHandle=window.DFL.showModal(React.createElement(window.DFL.ModalRoot,{
  onOK:()=>{
    child=window.DFL.showModal(React.createElement('p',{},'Details'));
    return new Promise(resolve=>{finish=resolve;});
  }}));
tree=render(published());
const nested=nodes(tree,'button')[0].props.onClick({});
assert.equal(modalRoot.tree.length,2);
assert.equal(nodes(modalRoot.tree[0],'button')[0].props.disabled,true);
assert.equal(nodes(modalRoot.tree[1],'button')[0].props.disabled,false);
nodes(modalRoot.tree[1],'button')[0].props.onClick();await child.ClosedPromise;
assert.equal(modalRoot.tree.length,1);
finish();await nested;
assert.equal(nodes(modalRoot.tree[0],'button')[0].props.disabled,false);
parentHandle.Close();await parentHandle.ClosedPromise;
const throwing=React.createElement(window.DFL.ModalRoot,{onOK:()=>{throw Error('Synthetic validation error');}});
const failedState=[];tree=render(throwing,failedState);
nodes(tree,'button')[0].props.onClick({});tree=render(throwing,failedState);
assert.equal(nodes(tree,'p').find(node=>node.props.role==='alert').children[0],'Synthetic validation error');
// Synchronous plugin code can reenter before returning its result. Suppress
// only that overlapping call: an open root may submit again after success.
let repeats=0,repeat;
tree=render(React.createElement(window.DFL.ModalRoot,{onOK:()=>{if(++repeats===1)repeat({});}}));
repeat=nodes(tree,'button')[0].props.onClick;
repeat({});assert.equal(repeats,1,'synchronous submission reentered');
repeat({});assert.equal(repeats,2,'an open root must stay retryable after synchronous success');
