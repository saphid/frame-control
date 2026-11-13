import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8');
const host=source.replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n})();');
assert.notEqual(host,source);
let active;
const React={Fragment:'fragment',Component:class {},forwardRef:render=>render,
  createElement:(type,props,...children)=>({type,props:{...props,
    ...(children.length?{children:children.length===1?children[0]:children}:{})},children}),
  cloneElement:(element,props)=>({...element,props:{...element.props,...props}}),
  useState:initial=>{
    const owner=active,index=owner.cursor++;
    if(!(index in owner.slots))owner.slots[index]=typeof initial==='function'?initial():initial;
    return [owner.slots[index],value=>{owner.slots[index]=typeof value==='function'?value(owner.slots[index]):value;}];
  },
  useRef:initial=>{const index=active.cursor++;return active.slots[index]??={current:initial};},
  useEffect:(effect,deps)=>{
    const index=active.cursor++;
    if(!(index in active.slots)){active.slots[index]=deps;active.effects.push(effect);}
  },isValidElement:value=>!!value?.type};
const roots=new Map(),elements=new Map();
const window={React,ReactDOM:{createRoot:element=>{
  const root={render(value){this.value=value;}};roots.set(element,root);return root;
}}};
const messages=[];
const context=vm.createContext({window,navigator:{language:'en'},document:{getElementById:id=>{
  if(!elements.has(id))elements.set(id,{});return elements.get(id);
}},
  parent:{postMessage:message=>messages.push(message)},addEventListener(){},setTimeout:()=>1,clearTimeout(){}});
vm.runInContext(host,context);
const saved=[];
Object.assign(context,{deckyFrontendLib:window.DFL,curColorHSLArray:[210,40,30,0.75],data:{name:'Accent colour'},
  setComponentAndReload:colour=>saved.push(colour)});
// Evaluate the exact published CSS Loader element and callback, with a local
// setter in place of theme changes. No plugin initializer/backend/Steam runs.
const published=vm.runInContext(readFileSync(0,'utf8'),context);
assert.equal(typeof published.type,'function','published ColorPickerModal must resolve to a Framey control');
const nodes=(tree,type)=>Array.isArray(tree)?tree.flatMap(child=>nodes(child,type)):
  [...(tree?.type===type?[tree]:[]),...(tree?.children||[]).flatMap(child=>nodes(child,type))];
const harness=component=>({slots:[],cursor:0,effects:[],cleanups:[],
  render(props){active=this;this.cursor=0;const tree=component(props);active=null;
    for(const effect of this.effects.splice(0)){const cleanup=effect();if(cleanup)this.cleanups.push(cleanup);}
    return tree;},unmount(){for(const cleanup of this.cleanups.splice(0))cleanup();}});
const mount=(props=published.props)=>{
  const picker=harness(published.type),confirm=harness(window.DFL.ConfirmModal),busy=[];
  let closed=false,element;
  const close=()=>{if(!closed){closed=true;picker.unmount();}};
  const render=()=>{element=picker.render({...props,closeModal:close,frameySetModalBusy:value=>busy.push(value)});
    return confirm.render(element.props);};
  return {render,picker,busy,get element(){return element;},get closed(){return closed;}};
};
const sliders=dialog=>nodes(dialog.element,window.DFL.SliderField);
const button=(tree,text)=>nodes(tree,'button').find(node=>node.children.includes(text));
const tick=()=>new Promise(resolve=>setImmediate(resolve));

let dialog=mount(),tree=dialog.render();
assert.deepEqual(sliders(dialog).map(node=>node.props.value),[210,40,30,0.75]);
assert.equal(dialog.element.props.strTitle,'Accent colour');
const retainedSubmit=button(tree,'OK').props.onClick;
sliders(dialog)[0].props.onChange(225);sliders(dialog)[3].props.onChange(0.5);
tree=dialog.render();
assert.deepEqual(saved,[],'moving sliders must not save');
assert.equal(nodes(dialog.element,'div').find(node=>node.props.role==='img').props.style.backgroundColor,
  'hsla(225, 40%, 30%, 0.5)');
await retainedSubmit();
assert.deepEqual(saved,['hsla(225, 40%, 30%, 0.5)'],'published callback must receive the latest draft once');
assert.equal(dialog.closed,true);

dialog=mount();tree=dialog.render();
const oldSubmit=button(tree,'OK').props.onClick,oldChange=sliders(dialog)[0].props.onChange;
oldChange(80);button(tree,'Cancel').props.onClick();
oldChange(90);await oldSubmit();
assert.equal(saved.length,1,'cancelled or retired controls must not save');

// Programmatic/shell closure removes the real host registration before React
// cleanup. A retained callback cannot write in that interval either.
const handle=window.DFL.showModal(published);
const bound=nodes(roots.get(elements.get('framey-modal')).value,published.type)[0];
const boundPicker=harness(published.type),boundConfirm=harness(window.DFL.ConfirmModal);
const boundElement=boundPicker.render(bound.props);
const boundTree=boundConfirm.render(boundElement.props);
handle.Close();
await button(boundTree,'OK').props.onClick();
assert.equal(saved.length,1,'closed host registration must retire writes before effect cleanup');
boundPicker.unmount();

// A returned promise keeps the local draft busy and allows a visible retry.
let writes=0,accept,reject,received;
dialog=mount({...published.props,onConfirm:colour=>{
  writes++;received=colour;return new Promise((resolve,fail)=>{accept=resolve;reject=fail;});
}});
tree=dialog.render();const edit=sliders(dialog)[0].props.onChange;
const submit=button(tree,'OK').props.onClick;
const pending=submit();submit();edit(60);tree=dialog.render();
assert.equal(writes,1);assert.equal(received,'hsla(210, 40%, 30%, 0.75)');
assert.ok(sliders(dialog).every(node=>node.props.disabled));
assert.equal(sliders(dialog)[0].props.value,210,'busy controls cannot edit the submitted draft');
assert.equal(button(tree,'Cancel').props.disabled,true);
button(tree,'Cancel').props.onClick();assert.equal(dialog.closed,false);
reject(Error('Synthetic save refused'));await pending;tree=dialog.render();
assert.equal(nodes(tree,'p').find(node=>node.props.role==='alert').children[0],'Synthetic save refused');
assert.equal(dialog.closed,false);assert.ok(sliders(dialog).every(node=>!node.props.disabled));
sliders(dialog)[0].props.onChange(240);tree=dialog.render();
const retry=button(tree,'OK').props.onClick();accept();await retry;
assert.equal(writes,2);assert.equal(received,'hsla(240, 40%, 30%, 0.75)');assert.equal(dialog.closed,true);
assert.deepEqual(dialog.busy,[true,false,true,false]);

// Invalid defaults and direct invalid slider calls cannot emit invalid HSLA.
dialog=mount({defaultH:NaN,defaultS:-10,defaultL:1000,defaultA:Infinity});dialog.render();
assert.deepEqual(sliders(dialog).map(node=>node.props.value),[0,0,100,1]);
sliders(dialog)[0].props.onChange(Infinity);sliders(dialog)[3].props.onChange(-1);dialog.render();
assert.deepEqual(sliders(dialog).map(node=>node.props.value),[0,0,100,1]);
dialog.picker.unmount();
assert.equal(messages.filter(message=>message.type==='framey:call').length,0);
await tick();
console.log('Published CSS Loader colour callback, draft/cancel and async retry pass; no theme/backend/VR proof.');
