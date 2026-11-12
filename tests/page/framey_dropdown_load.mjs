// The published Wine Cellar callback runs unchanged; only its read reply is synthetic.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const fixture=JSON.parse(readFileSync(0,'utf8'));
const source=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8');
const host=source.replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n})();');
assert.notEqual(host,source);
let slots=[],cursor=0,effects=[],cleanups=[];
const React={Fragment:'fragment',Component:class {},forwardRef:render=>render,
  createElement:(type,props,...children)=>({type,props:props||{},children}),
  useCallback:fn=>fn,
  useState:initial=>{
    const index=cursor++;
    if(!(index in slots))slots[index]=initial;
    return [slots[index],next=>{slots[index]=typeof next==='function'?next(slots[index]):next;}];
  },
  useRef:initial=>{const index=cursor++;return slots[index]??=({current:initial});},
  useEffect:(effect,deps)=>{
    const index=cursor++;
    if(!slots[index]||deps.some((value,i)=>value!==slots[index][i])){
      slots[index]=deps;effects.push(effect);
    }
  }};
const window={React,ReactDOM:{createRoot:()=>({render(){}})},location:{hash:''}};
const messages=[];
const context=vm.createContext({window,SP_REACT:React,navigator:{language:'en'},
  document:{getElementById:()=>({})},parent:{postMessage:message=>messages.push(message)},
  addEventListener(){},setTimeout:()=>1,clearTimeout(){},console});
vm.runInContext(host,context);
const nodes=(tree,type)=>Array.isArray(tree)?tree.flatMap(child=>nodes(child,type)):
  [...(tree?.type===type?[tree]:[]),...(tree?.children||[]).flatMap(child=>nodes(child,type))];
let replies=[],reads=[];
Object.assign(context,{toolOptions:{},toolLoads:{current:new Map()},toolCacheGeneration:{current:0},
  isMounted:{current:true},visibleApplicationKeys:{current:new Set(['42'])},
  applicationKey:app=>String(app.appId),errorMessage:error=>error.message,
  setToolOptions:update=>{context.toolOptions=update(context.toolOptions);},
  GetAvailableCompatTools:id=>{reads.push(id);return new Promise((resolve,reject)=>replies.push({resolve,reject}));},
  requestAnimationFrame:callback=>callback()});
vm.runInContext(fixture.callback+'\nwindow.__openToolMenu=openToolMenu;',context);
const props={label:'Compatibility tool',strDefaultLabel:'Choose tool',rgOptions:[],selectedOption:'',
  menuLabel:'Compatibility tool for Private fixture',
  onMenuWillOpen:showMenu=>{void window.__openToolMenu({appId:42},showMenu);},onChange:()=>{}};
const shell=window.DFL.Dropdown(props);
const component=shell.children.find(child=>typeof child?.type==='function');
assert.ok(component,'a deferred dropdown must expose Load options instead of skipping the plugin callback');
function render(next=props){
  cursor=0;
  const tree=component.type(next);
  for(const effect of effects.splice(0)){const cleanup=effect();if(cleanup)cleanups.push(cleanup);}
  return tree;
}
let tree=render();
assert.equal(nodes(tree,'select').length,0,'unprepared choices must stay hidden');
const load=nodes(tree,'button').find(button=>button.children.includes('Load options'));
assert.ok(load,'published onMenuWillOpen needs an explicit reachable action');
load.props.onClick();load.props.onClick();
await Promise.resolve();
assert.deepEqual(reads,[42],'rapid taps must invoke one published tool read');
tree=render();
assert.equal(nodes(tree,'select').length,0,'wait for showMenu, not just the initial tap');
assert.equal(nodes(tree,'button')[0].props.disabled,true);
replies.shift().resolve([{name:'Fixture Proton'}]);
await new Promise(resolve=>setImmediate(resolve));
assert.equal(context.toolOptions['42'].status,'ready');
const option={label:'Fixture Proton',data:'fixture-proton'};
let selected;
props.rgOptions=[option];props.onChange=entry=>{selected=entry;};
tree=render();
const select=nodes(tree,'select')[0];assert.ok(select,'showMenu exposes the freshly loaded choices');
assert.equal(select.props['aria-label'],'Compatibility tool for Private fixture');
select.props.onChange({target:{value:'0'}});
assert.equal(selected,option,'selection keeps the original Decky option object');

// The published loader catches read failures itself and does not call showMenu.
// Preserve that contract while offering an explicit way out of the wait.
context.toolOptions={};
tree=render();nodes(tree,'button')[0].props.onClick();await Promise.resolve();
replies.shift().reject(Error('fixture tool read failed'));
await new Promise(resolve=>setImmediate(resolve));
assert.equal(context.toolOptions['42'].status,'error');
tree=render();assert.equal(nodes(tree,'select').length,0);
nodes(tree,'button').find(button=>button.children.includes('Cancel loading')).props.onClick();
tree=render();nodes(tree,'button')[0].props.onClick();await Promise.resolve();
replies.shift().resolve([{name:'Fixture Proton'}]);
await new Promise(resolve=>setImmediate(resolve));
tree=render();assert.equal(nodes(tree,'select').length,1);
assert.deepEqual(reads,[42,42,42]);

// A void-returning callback may report its own failure without calling showMenu.
// The user can cancel the wait and retry; late callbacks cannot reopen it.
let showLate,opens=0;
props.onMenuWillOpen=showMenu=>{opens++;showLate=showMenu;};
tree=render();nodes(tree,'button')[0].props.onClick();
tree=render();
const staleSelect=select;
selected=null;staleSelect.props.onChange({target:{value:'0'}});assert.equal(selected,null);
const cancel=nodes(tree,'button').find(button=>button.children.includes('Cancel loading'));
assert.ok(cancel);cancel.props.onClick();showLate();
tree=render();assert.equal(nodes(tree,'select').length,0);
nodes(tree,'button')[0].props.onClick();tree=render();showLate();
tree=render();assert.equal(nodes(tree,'select').length,1);assert.equal(opens,2);

// Disabled, synchronous error, rejected promise, retry and disposal guards.
props.disabled=true;tree=render();
assert.equal(nodes(tree,'button')[0].props.disabled,true);
nodes(tree,'button')[0].props.onClick();assert.equal(opens,2);
nodes(tree,'select')[0].props.onChange({target:{value:'0'}});assert.equal(selected,null);
props.disabled=false;props.onMenuWillOpen=()=>{throw Error('read failed');};
tree=render();nodes(tree,'button')[0].props.onClick();tree=render();
assert.equal(nodes(tree,'select').length,0);
assert.equal(nodes(tree,'p').find(node=>node.props.role==='alert').children[0],'read failed');
props.onMenuWillOpen=showMenu=>{showLate=showMenu;return Promise.reject(Error('offline'));};
tree=render();nodes(tree,'button')[0].props.onClick();await new Promise(resolve=>setImmediate(resolve));tree=render();
assert.equal(nodes(tree,'p').find(node=>node.props.role==='alert').children[0],'offline');
showLate();tree=render();assert.equal(nodes(tree,'select').length,0,'a late showMenu cannot erase failure');
props.onMenuWillOpen=()=>Promise.resolve();
tree=render();nodes(tree,'button')[0].props.onClick();await Promise.resolve();tree=render();
assert.equal(nodes(tree,'select').length,0,'a resolved return value does not replace showMenu');
nodes(tree,'button').find(button=>button.children.includes('Cancel loading')).props.onClick();
props.onMenuWillOpen=showMenu=>{showLate=showMenu;};
tree=render();nodes(tree,'button')[0].props.onClick();
const retainedLoad=nodes(tree,'button')[0].props.onClick;
for(const cleanup of cleanups)cleanup();
const before=JSON.stringify(slots);showLate();retainedLoad();assert.equal(JSON.stringify(slots),before);
assert.equal(messages.filter(message=>message.type==='framey:call').length,0,
  'isolated published callback fixture must not invoke a live backend or helper');
