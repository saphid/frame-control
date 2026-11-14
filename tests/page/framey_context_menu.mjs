import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8');
const host=source.replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n})();');
assert.notEqual(host,source);
const React={Fragment:'fragment',Component:class {},forwardRef:render=>render,
  createElement:(type,props,...children)=>({type,props:props||{},children}),
  cloneElement:(element,props)=>({...element,props:{...element.props,...props}}),
  isValidElement:element=>!!element?.type};
const roots=new Map(),elements=new Map();
const window={React,ReactDOM:{createRoot:node=>{
  const root={render(value){this.value=value;}};roots.set(node,root);return root;
}}};
const context=vm.createContext({window,navigator:{language:'en'},parent:{postMessage(){}},
  document:{getElementById:id=>{
    if(!elements.has(id))elements.set(id,{});return elements.get(id);
  }},addEventListener(){},setTimeout(){},clearTimeout(){}});
vm.runInContext(host,context);
const modalRoot=roots.get(elements.get('framey-modal'));
Object.assign(context,{DFL:window.DFL,LibraryMenu:()=>null});
vm.runInContext(readFileSync(0,'utf8'),context);
const manager={privateFixture:true};
context.getShowMenu('private-tab',manager)();
assert.equal(modalRoot.value.length,1);
const menu=modalRoot.value[0].children[1].children[0];
assert.equal(menu.props.selectedTabId,'private-tab');
assert.equal(menu.props.tabMasterManager,manager);
// Replay the exact published closure. The actual library menu and manager
// never execute, so no Steam library mutation is implied.
menu.props.closeMenu();
assert.equal(modalRoot.value,null,'published Hide must close its own menu');
const handle=window.DFL.showContextMenu(React.createElement('div',null,'Fixture menu'));
assert.equal(typeof handle.Hide,'function');assert.equal(typeof handle.Show,'function');
handle.Show();handle.Show();assert.equal(modalRoot.value.length,1);
const nested=window.DFL.showModal(React.createElement('div',null,'Nested dialog'));
assert.equal(modalRoot.value.length,2);
handle.Hide();handle.Hide();assert.equal(modalRoot.value.length,1);
assert.equal(modalRoot.value[0].children[1].children[0].children[0],'Nested dialog');
nested.Close();assert.equal(modalRoot.value,null);
handle.Show();assert.equal(modalRoot.value.length,1);
// Shell dismissal and Show can occur in the same turn, before any promise
// callbacks run. Visibility must use actual membership in the modal stack.
modalRoot.value[0].children[0].props.onClick();assert.equal(modalRoot.value,null);
handle.Show();assert.equal(modalRoot.value.length,1);
handle.Hide();assert.equal(modalRoot.value,null);
