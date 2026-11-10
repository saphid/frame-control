import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8');
const host=source.replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n})();');
assert.notEqual(host,source);
const React={Fragment:'fragment',Component:class {},forwardRef:render=>render,
  createElement:(type,props,...children)=>({type,props:{...props,
    ...(children.length?{children:children.length===1?children[0]:children}:{})},children})};
const window={React,ReactDOM:{createRoot:()=>({render(){}})},
  MicroSDeck:{CardsAndGames:[[{uid:'private-card',name:'Private fixture card'},[]]]}};
const context=vm.createContext({window,navigator:{language:'en'},document:{getElementById:()=>({})},
  parent:{postMessage:message=>assert.equal(message.type,'framey:cache:init')},
  addEventListener(){},setTimeout(){},clearTimeout(){}});
vm.runInContext(host,context);
const writes=[];
Object.assign(context,{DFL:window.DFL,isMicroSDeckInstalled:false,presetName:'micro sd card',
  getActionDescription:()=>({}),tabMasterManager:{createPresetTab:(...args)=>writes.push(args)}});
// Only the pinned preset-menu expression runs. The manager and card metadata
// are synthetic; no real library editing, card discovery or backend runs.
const expression=readFileSync(0,'utf8');
const published=()=>vm.runInContext(expression,context);
const expand=tree=>Array.isArray(tree)?tree.map(expand):!tree||typeof tree!=='object'?tree:
  typeof tree.type==='function'?expand(tree.type(tree.props)):
  {...tree,children:tree.children.map(expand)};
const nodes=(tree,type)=>Array.isArray(tree)?tree.flatMap(child=>nodes(child,type)):
  [...(tree?.type===type?[tree]:[]),...(tree?.children||[]).flatMap(child=>nodes(child,type))];
let tree=expand(published());
const groups=nodes(tree,'fieldset');
assert.equal(groups.length,2,'published MenuGroup must use native disabled inheritance');
assert.equal(groups[0].props.disabled,true);
assert.equal(groups[1].props.disabled,false,'nested group can inherit its disabled ancestor');
assert.deepEqual(nodes(tree,'legend').map(node=>node.children[0]),['Micro SD Card','Specific Card']);
assert.deepEqual(nodes(tree,'button').map(node=>node.children[0]),['Inserted Card','Private fixture card']);
assert.deepEqual(writes,[]);
context.isMicroSDeckInstalled=true;
tree=expand(published());
assert.equal(nodes(tree,'fieldset')[0].props.disabled,false);
nodes(tree,'button')[1].props.onClick({});
assert.deepEqual(writes,[['micro sd card','Private fixture card','private-card']]);
// Individual disabled menu items retain their own guard in an enabled group.
let attempts=0;
tree=expand(React.createElement(window.DFL.MenuGroup,{label:'Actions'},
  React.createElement(window.DFL.MenuItem,{disabled:true,onClick:()=>attempts++},'Unavailable')));
const button=nodes(tree,'button')[0];assert.equal(button.props.disabled,true);
button.props.onClick({});assert.equal(attempts,0);
