// Execute the pinned official HLTB frontend's entry point with Framey's API.
// This checks module startup only; it never makes network or backend calls.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {inflateRawSync} from 'node:zlib';
import vm from 'node:vm';

const host=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8');
const hostTest=host.replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n})();');
assert.notEqual(hostTest,host);
const zip=readFileSync(new URL('../fixtures/framey-official/26.zip',import.meta.url));
const eocd=zip.lastIndexOf(Buffer.from([0x50,0x4b,0x05,0x06]));
assert.ok(eocd>0);
let offset=zip.readUInt32LE(eocd+16),bundle;
for(let i=0;i<zip.readUInt16LE(eocd+10);i++){
  assert.equal(zip.readUInt32LE(offset),0x02014b50);
  const nameLength=zip.readUInt16LE(offset+28),extraLength=zip.readUInt16LE(offset+30);
  const commentLength=zip.readUInt16LE(offset+32);
  const name=zip.subarray(offset+46,offset+46+nameLength).toString();
  if(name==='hltb-for-deck/dist/index.js'){
    const local=zip.readUInt32LE(offset+42);
    assert.equal(zip.readUInt32LE(local),0x04034b50);
    const start=local+30+zip.readUInt16LE(local+26)+zip.readUInt16LE(local+28);
    const compressed=zip.subarray(start,start+zip.readUInt32LE(offset+20));
    bundle=(zip.readUInt16LE(offset+10)===8?inflateRawSync(compressed):compressed).toString();
  }
  offset+=46+nameLength+extraLength+commentLength;
}
assert.ok(bundle);
const official=bundle.replace(/export \{ index as default \};\s*\/\/# sourceMappingURL=index.js.map\s*$/,
  'window.__official = index;');
assert.notEqual(official,bundle);
const react=new Proxy({Fragment:'fragment',Component:class {},
  createElement:(type,props,...children)=>({type,props,children}),
  createContext:value=>({Provider:()=>{},Consumer:()=>{},_currentValue:value}),
  forwardRef:fn=>fn,memo:fn=>fn,useState:value=>[value,()=>{}],
  useContext:ctx=>ctx?._currentValue,useMemo:fn=>fn(),useCallback:fn=>fn,
  useRef:value=>({current:value}),useEffect(){}},
  {get:(target,key)=>target[key]??(()=>{})});
const window={React:react,ReactDOM:{createRoot:()=>({render(){}})},location:{hash:''}};
const elements=new Map();
const context=vm.createContext({window,navigator:{language:'en'},parent:{postMessage(){}},
  document:{getElementById:id=>{if(!elements.has(id))elements.set(id,{});return elements.get(id);}},
  addEventListener(){},setTimeout:()=>1,clearTimeout(){},console,URL,Blob});
vm.runInContext(hostTest,context);
context.DFL=window.DFL;
context.SP_REACT=window.SP_REACT;
context.SP_JSX=window.SP_JSX;
vm.runInContext(official,context,{timeout:2000});
const plugin=window.__official();
assert.equal(typeof window.DFL.findModuleChild,'function');
assert.equal(window.DFL.findModuleChild(()=>{}),undefined); // Steam has no matching module in the VR panel.
assert.equal(plugin.content?.type?.name,'QuickAccessView');
const panel=plugin.content.type();
assert.ok(panel?.type); // Read-only settings render with empty local data.
assert.equal(typeof plugin.onDismount,'function');
plugin.onDismount();
