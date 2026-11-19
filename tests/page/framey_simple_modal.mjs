import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8');
const host=source.replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n})();');
assert.notEqual(host,source);
const React={Fragment:'fragment',Component:class {constructor(props){this.props=props;}},forwardRef:render=>render,
  createElement:(type,props,...children)=>({type,props:{...props,
    ...(children.length?{children:children.length===1?children[0]:children}:{})},children}),
  cloneElement:(element,props)=>({...element,props:{...element.props,...props}}),
  isValidElement:element=>!!element?.type};
const elements=new Map(),roots=new Map(),listeners=[];
const window={React,SP_REACT:React,ReactDOM:{createRoot:node=>{
  const root={render:tree=>{root.tree=tree;}};roots.set(node,root);return root;
}}};
const context=vm.createContext({window,document:{getElementById:id=>{
  if(!elements.has(id))elements.set(id,{});return elements.get(id);}},navigator:{language:'en'},
  parent:{postMessage:message=>assert.equal(message.type,'framey:cache:init')},
  addEventListener:(type,handler)=>listeners.push({type,handler}),setTimeout(){},clearTimeout(){}});
vm.runInContext(host,context);
const DFL=window.DFL;
assert.equal(typeof DFL.SimpleModal,'function','published SimpleModal must resolve to a Framey control');
assert.equal(DFL.findModuleExport(value=>value===DFL.SimpleModal),DFL.SimpleModal);
assert.equal(DFL.findModuleExport(value=>value?.SteamPortalManager),undefined);
// Evaluate only the digest-verified warning component. Its callbacks record
// synthetic choices; no plugin initializer, browser tab or backend runs.
context.deckyFrontendLib=DFL;
vm.runInContext(readFileSync(0,'utf8')+'\nwindow.publishedModal=UsageWarningModal;',context);
const expand=tree=>Array.isArray(tree)?tree.map(expand):!tree||typeof tree!=='object'?tree:
  typeof tree.type==='function'?expand(tree.type.prototype instanceof React.Component
    ? new tree.type(tree.props).render() : tree.type(tree.props)):
  {...tree,children:tree.children.map(expand)};
const nodes=(tree,type)=>Array.isArray(tree)?tree.flatMap(child=>nodes(child,type)):
  [...(tree?.type===type?[tree]:[]),...(tree?.children||[]).flatMap(child=>nodes(child,type))];
const root=roots.get(elements.get('framey-modal'));
const choices=[];
const show=()=>DFL.showModal(React.createElement(window.publishedModal,{
  onOk:()=>choices.push('accept'),onCancel:()=>choices.push('cancel')}));
let handle=show(),tree=expand(root.tree);
assert.equal(nodes(tree,'h3')[0].children[0],'WARNING');
assert.match(nodes(tree,'p')[0].children[0],/known security vulnerabilities/);
assert.equal(nodes(tree,'p')[0].props.style.textAlign,'justify');
nodes(tree,'button').find(node=>node.children.includes('I Understand')).props.onClick();
await handle.ClosedPromise;
assert.deepEqual(choices,['accept']);assert.equal(root.tree,null);
handle=show();nodes(expand(root.tree),'button').find(node=>node.children.includes('Close')).props.onClick();
await handle.ClosedPromise;assert.deepEqual(choices,['accept','cancel']);
handle=show();listeners.find(listener=>listener.type==='keydown').handler({key:'Escape',preventDefault(){}});
await handle.ClosedPromise;assert.deepEqual(choices,['accept','cancel','cancel']);
handle=show();handle.Close();await handle.ClosedPromise;
assert.deepEqual(choices,['accept','cancel','cancel'],'programmatic Close is silent');
// Inactive children must not render or run effects. Omission defaults to an
// active local wrapper; host-injected close/busy props are never DOM props.
let renders=0;
const Child=()=>{renders++;return React.createElement('p',null,'Local content');};
assert.equal(expand(React.createElement(DFL.SimpleModal,{active:false},React.createElement(Child))),null);
assert.equal(renders,0);
tree=expand(React.createElement(DFL.SimpleModal,{},React.createElement(Child)));
assert.equal(nodes(tree,'p')[0].children[0],'Local content');assert.equal(renders,1);
