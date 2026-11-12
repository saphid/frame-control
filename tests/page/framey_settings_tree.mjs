// Exact published Emuchievements migration; all settings/RPC replies are synthetic.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8');
const host=source.replace(/\n  start\(\);\n\}\)\(\);\s*$/, '\n  window.__legacy=legacyServerAPI;\n})();');
assert.notEqual(host,source);
class Element {append(){} setAttribute(){} remove(){}}
const listeners=[],calls=[];
let saved,chunks=[],readBuffer;
const window={React:{Fragment:'fragment',Component:class {},forwardRef:render=>render,createElement:()=>({}),isValidElement:()=>false},
  ReactDOM:{createRoot:()=>({render(){}})}};
const parent={postMessage:message=>{
  if(message.type==='framey:cache:init')return;
  assert.equal(message.type,'framey:call');
  assert.equal(message.legacy,true,'migration must use the real legacy RPC envelope');
  const [args]=message.args;
  calls.push(message.method);
  let result;
  switch(message.method) {
    case 'start_read_config':
      readBuffer=saved;result=Math.ceil(readBuffer.length/args.packet_size);break;
    case 'read_config':result=readBuffer.slice(args.index*2048,(args.index+1)*2048);break;
    case 'start_write_config':chunks=new Array(args.length);result=true;break;
    case 'write_config':
      chunks[args.index]=args.data;
      if(chunks.filter(x=>x!==undefined).length===chunks.length)saved=chunks.join('');
      result=true;break;
    default:throw Error('Unexpected fixture method '+message.method);
  }
  queueMicrotask(()=>listeners.find(x=>x.type==='message').handler({source:parent,
    data:{type:'framey:reply',id:message.id,result:{success:true,result}}}));
}};
const context=vm.createContext({window,parent,navigator:{language:'en'},
  document:{getElementById:()=>new Element(),createElement:()=>new Element()},
  addEventListener:(type,handler)=>listeners.push({type,handler}),setTimeout:()=>1,clearTimeout(){},
  Logger:class {debug(){}},Mutex:class {async acquire(){return ()=>{};}},
  getTranslateFunc:()=>key=>key});
vm.runInContext(host,context);
context.deckyFrontendLib=window.DFL;
vm.runInContext(readFileSync(0,'utf8')+'\nwindow.__Settings=Settings;',context);

for(const values of [
  {username:'Public fixture user',api_key:'public-fixture-key'},
  {username:'',api_key:''},
]) {
  // A legacy nested file must retain values rather than fail with a missing API.
  saved=JSON.stringify({config_version:'old-fixture',legacy:{accounts:[{retroachievements:values}]}});
  calls.length=0;
  const first=new window.__Settings(window.__legacy,{notifyUpdate(){}});
  await first.readSettings();
  assert.deepEqual(JSON.parse(saved).retroachievements,values);
  assert.equal(JSON.parse(saved).config_version,'1.1.0');
  assert.deepEqual(calls,['start_read_config','read_config','start_write_config','write_config']);
  const snapshot=saved;calls.length=0;
  // Reopen the migrated settings through the same exact published read method.
  const reopened=new window.__Settings(window.__legacy,{notifyUpdate(){}});
  await reopened.readSettings();
  assert.deepEqual(JSON.parse(JSON.stringify(reopened.retroachievements)),values);
  assert.equal(saved,snapshot,'reading the current schema must not rewrite settings');
  assert.deepEqual(calls,['start_read_config','read_config']);
}

const {findInTree,findInReactTree}=window.DFL;
const first={match:true},second={match:true};
assert.equal(findInTree({nested:[first,second]},node=>node.match),first);
assert.equal(findInTree({skip:first,keep:[second]},node=>node.match,{ignore:['skip']}),second);
assert.equal(findInTree({skip:first,keep:[second]},node=>node.match,{walkable:['keep']}),second);
assert.equal(findInTree(null,()=>true),null);
const circular={};circular.self=circular;circular.children=[second];
assert.equal(findInTree(circular,node=>node.match),second,'cycles must not strand a later match');
assert.equal(findInTree(circular,()=>false),undefined,'a cyclic tree without a match must terminate');
assert.equal(findInReactTree({steamStore:first,props:{children:[second]}},node=>node.match),second);
assert.equal(window.DFL.getReactRoot(null),null,'the utility must not expose a Steam React root');
