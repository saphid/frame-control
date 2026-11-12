import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const host=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8')
  .replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n})();');
let slots=[],cursor=0;
const React={Fragment:'fragment',Component:class {},forwardRef:render=>render,
  createElement:(type,props,...children)=>({type,props:{...props,
    ...(children.length?{children:children.length===1?children[0]:children}:{})},children}),
  useState:initial=>{
    const index=cursor++;
    if (!(index in slots)) slots[index]=initial;
    return [slots[index],value=>{slots[index]=value;}];
  },useRef:value=>({current:value}),useEffect(){},useLayoutEffect(){},isValidElement:value=>!!value?.type};
const window={React,ReactDOM:{createRoot:()=>({render(){}})}};
const context=vm.createContext({window,document:{getElementById:()=>({})},
  navigator:{language:'en'},parent:{postMessage(){}},addEventListener(){},setTimeout(){},clearTimeout(){}});
vm.runInContext(host,context);
const nodes=(tree,type)=>Array.isArray(tree)?tree.flatMap(child=>nodes(child,type)):
  [...(tree?.type===type?[tree]:[]),...(tree?.children||[]).flatMap(child=>nodes(child,type))];

// Evaluate the exact published Game Sync navigation class, not its backend or
// child views. Effects, data reads, sync actions and file operations never run.
const unavailable=()=>{throw Error('No backend or sync action expected');};
Object.assign(context,{DFL:{...window.DFL,useParams:()=>({appId:'42'})},SP_REACT:React,SP_JSX:window.SP_JSX,
  RoutePage:class {},getAppName:()=> 'Private game',syncTaskQueue:{busy:false},GLOBAL_SYNC_APP_ID:0,
  LogsView:unavailable,filtersView:unavailable,sharedFiltersView:unavailable,
  iconButton:unavailable,FaCloudArrowUp:unavailable,FaCloudArrowDown:unavailable});
vm.runInContext(readFileSync(0,'utf8'),context);
const published=vm.runInContext('new SyncTargetConfigPage().render()',context);
const pages=published.props.pages;
assert.equal(pages[1],'separator');
const original=[...pages];
slots=[];
const render=props=>{
  cursor=0;
  const sidebar=window.DFL.SidebarNavigation(props);
  const tabs=nodes(sidebar,window.DFL.Tabs)[0];
  return tabs.type(tabs.props);
};
const titles=tree=>nodes(tree,'button').map(button=>button.children[0]);
const selected=tree=>nodes(tree,'button').filter(button=>button.props['aria-selected']);
const panel=tree=>nodes(tree,'div').find(node=>node.props.role==='tabpanel').children[0];
let tree=render(published.props);
assert.deepEqual(titles(tree),['Sync Logs','Target Filter','Shared Filter'],
  'published separator must not create a blank selectable tab');
for (const [index,page] of [pages[0],pages[2],pages[3]].entries()) {
  nodes(tree,'button')[index].props.onClick();
  tree=render(published.props);
  assert.equal(selected(tree).length,1);
  assert.equal(selected(tree)[0].children[0],page.title);
  assert.equal(panel(tree),page.content,'selecting a real page preserves its published content');
}
assert.deepEqual([...pages],original,'navigation must not mutate the published pages');

// Separators at either edge or next to hidden pages never become an empty
// destination. Retained index identities keep the selected page when an
// earlier page changes visibility.
slots=[];
const a={title:'A',content:'A content'},b={title:'B',content:'B content'},c={title:'C',content:'C content'};
let props={pages:['separator',a,'separator',b,'separator',c,'separator']};
tree=render(props);
assert.deepEqual(titles(tree),['A','B','C']);
nodes(tree,'button')[1].props.onClick();
props={pages:['separator',{...a,visible:false},'separator',b,'separator',c,'separator']};
tree=render(props);
assert.deepEqual(titles(tree),['B','C']);
assert.equal(selected(tree)[0].children[0],'B');
assert.equal(panel(tree),'B content');
props={pages:['separator',{...a,visible:false},'separator',{...b,visible:false},'separator',c,'separator']};
tree=render(props);
assert.deepEqual(titles(tree),['C']);
assert.equal(panel(tree),'C content','hiding the active page falls back to a visible page');
tree=render({pages:['separator',{...a,visible:false},'separator']});
assert.deepEqual(titles(tree),[]);
assert.equal(panel(tree),undefined);
console.log('Published Game Sync sidebar pages navigate without blank separator tabs; backend and VR unverified.');
