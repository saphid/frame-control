import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8');
const host=source.replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n})();');
assert.notEqual(host,source);
const React={Fragment:'fragment',Component:class {},
  createElement:(type,props,...children)=>({type,props:{...props,
    ...(children.length?{children:children.length===1?children[0]:children}:{})},children}),
  useRef:value=>({current:value}),useState:value=>[value,()=>{}],useEffect(){}};
const window={React,ReactDOM:{createRoot:()=>({render(){}})}};
const context=vm.createContext({window,navigator:{language:'en'},document:{getElementById:()=>({})},
  parent:{postMessage:message=>assert.equal(message.type,'framey:cache:init')},
  addEventListener(){},setTimeout(){},clearTimeout(){}});
vm.runInContext(host,context);
let reads=0,writes=0;
Object.assign(context,{DFL:window.DFL,availableTools:[],assignedToolName:'private-proton',
  assignedToolDisplayName:'Synthetic assigned Proton',compatibilityMappingsStale:false,
  application:{appId:424242,name:'Private fixture'},
  dropdownOptions:()=>[],openToolMenu:()=>reads++,selectCompatTool:()=>writes++});
// Evaluate only the pinned control and its current-value renderer. Do not run
// the plugin initializer, real tool discovery, backend or assignment methods.
const element=vm.runInContext(readFileSync(0,'utf8'),context);
const expand=tree=>Array.isArray(tree)?tree.map(expand):!tree||typeof tree!=='object'?tree:
  typeof tree.type==='function'?expand(tree.type(tree.props)):
  {...tree,children:tree.children.map(expand)};
const nodes=(tree,type)=>Array.isArray(tree)?tree.flatMap(child=>nodes(child,type)):
  [...(tree?.type===type?[tree]:[]),...(tree?.children||[]).flatMap(child=>nodes(child,type))];
let tree=expand(element);
let value=nodes(tree,'span').find(node=>node.props.title==='Synthetic assigned Proton');
assert.ok(value,'published renderButtonValue must show the assigned tool before options are loaded');
assert.equal(value.props['aria-label'],'Compatibility tool for Private fixture: Synthetic assigned Proton');
assert.equal(value.props.style.textOverflow,'ellipsis');
assert.equal(nodes(tree,'select').length,0,'a current value must not bypass the loading gate');
assert.equal(reads,0);assert.equal(writes,0);
tree=expand(React.createElement(window.DFL.Dropdown,{...element.props,disabled:true}));
assert.equal(nodes(tree,'span')[0].props.title,'Synthetic assigned Proton');
nodes(tree,'button')[0].props.onClick();assert.equal(reads,0);

// Match option.data rather than truthiness, and pass its original React label.
const rich=React.createElement('strong',null,'Zero mode');
const choices=[{label:'Modes',options:[{label:rich,data:0},{label:'Default mode',data:''}]}];
let received,selected;
const renderButtonValue=label=>{received=label;return React.createElement('span',{title:'Current value'},label);};
tree=expand(React.createElement(window.DFL.Dropdown,{rgOptions:choices,selectedOption:0,
  renderButtonValue,onChange:entry=>{selected=entry;}}));
assert.equal(received,rich);
assert.ok(nodes(tree,'strong').some(node=>node.children.includes('Zero mode')));
nodes(tree,'select')[0].props.onChange({target:{value:'1'}});
assert.equal(selected,choices[0].options[1],'native selection keeps the original option');
expand(React.createElement(window.DFL.Dropdown,{rgOptions:choices,selectedOption:'',renderButtonValue}));
assert.equal(received,'Default mode');
expand(React.createElement(window.DFL.Dropdown,{rgOptions:choices,selectedOption:'missing',
  strDefaultLabel:'Choose mode',renderButtonValue}));
assert.equal(received,'Choose mode');
tree=expand(React.createElement(window.DFL.Dropdown,{rgOptions:choices,selectedOption:0}));
assert.equal(nodes(tree,'span').length,0,'ordinary dropdowns must not acquire a custom value row');
