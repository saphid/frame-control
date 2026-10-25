import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8');
const testSource=source.replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n  window.__surface=PluginSurface;\n})();');
assert.notEqual(testSource,source);
const states=[];
const React={Fragment:'fragment',Component:class {},createElement:(type,props,...children)=>({type,props:props||{},children}),
  useState:value=>[value,next=>states.push(next)]};
const window={React,ReactDOM:{createRoot:()=>({render(){}})},addEventListener(){}};
const context=vm.createContext({window,document:{getElementById:()=>({})},navigator:{language:'en'},
  parent:{postMessage(){}},addEventListener(){},setTimeout(){},clearTimeout(){}});
vm.runInContext(testSource,context);
const nodes=(tree,type)=>[...(tree?.type===type?[tree]:[]),...(tree?.children||[]).flatMap(child=>nodes(child,type))];
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
