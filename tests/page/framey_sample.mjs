import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const host=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8')
  .replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n})();');
const bundle=readFileSync(new URL('../../examples/framey-settings/dist/index.js',import.meta.url),'utf8');
assert.match(bundle,/SP_JSX\.jsx/);
const React={Fragment:Symbol('fragment'),Component:class {},
  createElement:(type,props,...children)=>({type,props:props||{},children}),
  useState:value=>[value,()=>{}],useEffect(){},isValidElement:value=>!!value?.type};
const window={React,ReactDOM:{createRoot:()=>({render(){}})},addEventListener(){}};
const context=vm.createContext({window,document:{getElementById:()=>({})},
  navigator:{language:'en'},parent:{postMessage(){}},addEventListener(){},
  setTimeout:()=>1,clearTimeout(){}});
vm.runInContext(host,context);
Object.assign(context,{SP_REACT:window.SP_REACT,SP_JSX:window.SP_JSX,DFL:window.DFL});
vm.runInContext(bundle.replace(/export \{ index as default \};/, 'window.sample = index;'),context);
const plugin=window.sample();
assert.equal(plugin.name,'Framey Settings Sample');
assert.equal(typeof plugin.content.type,'function');
const content=plugin.content.type();
assert.equal(content.type,window.DFL.PanelSection);
assert.equal(content.props.title,'Framey settings sample');
assert.equal(content.children[0][0].type,window.DFL.PanelSectionRow);
