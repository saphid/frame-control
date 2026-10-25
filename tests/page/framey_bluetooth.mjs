// Start the unmodified official Bluetooth frontend and build its initial UI.
// Effects and click handlers are inert: no Bluetooth/backend operation runs.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const bundle=readFileSync(process.argv[2],'utf8');
const official=bundle.replace(/export \{ index as default \};\s*\/\/# sourceMappingURL=index.js.map\s*$/,
  'window.__official = index;');
assert.notEqual(official,bundle);
const source=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8');
const host=source.replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n})();');
assert.notEqual(host,source);
const react=new Proxy({Fragment:'fragment',Component:class {},
  createElement:(type,props,...children)=>({type,props,children}),
  createContext:value=>({Provider:()=>{},Consumer:()=>{},_currentValue:value}),
  useState:value=>[value,()=>{}],useReducer:(_,value)=>[value,()=>{}],
  useEffect(){},useRef:value=>({current:value}),useMemo:fn=>fn(),
  useCallback:fn=>fn,forwardRef:fn=>fn,memo:fn=>fn},
  {get:(target,key)=>target[key]??(()=>{})});
const window={React:react,ReactDOM:{createRoot:()=>({render(){}})},location:{hash:''}};
const elements=new Map();
const messages=[];
const context=vm.createContext({window,navigator:{language:'en'},parent:{postMessage:message=>messages.push(message)},
  document:{getElementById:id=>{if(!elements.has(id))elements.set(id,{});return elements.get(id);}},
  addEventListener(){},setTimeout:()=>1,clearTimeout(){},console,URL,Blob});
vm.runInContext(host,context);
context.DFL=window.DFL;
context.SP_REACT=window.SP_REACT;
context.SP_JSX=window.SP_JSX;
context.LocalizationManager=window.LocalizationManager;
assert.equal(window.LocalizationManager.m_mapTokens.size,0);
assert.equal(window.LocalizationManager.m_mapFallbackTokens.get('Settings_Bluetooth_Devices'),'Devices');
vm.runInContext(official,context,{timeout:2000});
const plugin=window.__official();
assert.equal(plugin.content?.type?.name,'Content');
const panel=plugin.content.type();
assert.equal(panel.type,'div');
const text=JSON.stringify(panel);
assert.match(text,/Bluetooth/);
assert.match(text,/Devices/); // Readable fallback when Steam tokens are absent.
assert.doesNotMatch(text,/Settings_Bluetooth_Devices/);
assert.equal(messages.filter(message=>message.type==='framey:call').length,0);
