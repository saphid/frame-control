// Exercise the exact managed Storage Cleaner async action with private RPCs.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const bundle=readFileSync(process.argv[2],'utf8');
const start=bundle.indexOf('    async function clearDataCache(');
const end=bundle.indexOf('    // Templates',start);
assert.ok(start>0 && end>start);
const calls=[];
const pending=[];
const context=vm.createContext({call:(method,path)=>{
  assert.equal(method,'delete_cache');
  calls.push(path);
  return new Promise((resolve,reject)=>pending.push({resolve,reject}));
}});
vm.runInContext(bundle.slice(start,end)+'\nglobalThis.clearDataCache=clearDataCache;',context);

let settled=false;
const selected=context.clearDataCache('shadercache',['424242','424243']).then(()=>{settled=true;});
assert.deepEqual(calls,['shadercache/424242']);
pending[0].resolve();
await new Promise(resolve=>setImmediate(resolve));
assert.deepEqual(calls,['shadercache/424242','shadercache/424243']);
assert.equal(settled,false);
pending[1].resolve();
await selected;
assert.equal(settled,true);

const failed=context.clearDataCache('compatdata',['1','2']);
assert.equal(calls.at(-1),'compatdata/1');
pending[2].reject(new Error('private RPC failed'));
await assert.rejects(failed,/private RPC failed/);
assert.equal(calls.includes('compatdata/2'),false);

const whole=context.clearDataCache('compatdata');
assert.equal(calls.at(-1),'compatdata');
pending[3].resolve();
await whole;
