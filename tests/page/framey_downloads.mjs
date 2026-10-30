import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source=readFileSync(new URL('../../ui/framey-downloads.js',import.meta.url),'utf8');
const callbacks=new Set(),intervals=new Map(),methodTimers=new Map(),calls=[];let now=1000,next=0;
const row=(appid,size=100,queue_index=-1)=>({appid,queue_index,completed:false,deferred_time:10,
  private_token:'PRIVATE',update_type_info:[{has_update:true,progress:[{bytes_total:size,private_path:'PRIVATE'}]}]});
const api={RegisterForDownloadItems(fn){callbacks.add(fn);return {unregister:()=>callbacks.delete(fn)};},
  QueueAppUpdate:async(...args)=>{calls.push(['queue',...args]);},
  SetQueueIndex:async(...args)=>{calls.push(['index',...args]);},
  ResumeAppUpdate:async(...args)=>{calls.push(['resume',...args]);}};
const window={SteamClient:{Downloads:api}};
const context=vm.createContext({window,Date:{now:()=>now},
  setTimeout:fn=>{methodTimers.set(++next,fn);return next;},clearTimeout:key=>methodTimers.delete(key),
  setInterval:fn=>{intervals.set(++next,fn);return next;},clearInterval:id=>intervals.delete(id)});
const run=(action='read',appids=null,session='one',revision=window.__frameyDownloadsBridgeV1?.sessions.get(session)?.version)=>
  vm.runInContext(source,context)({action,appids,session,revision});
const emit=(items,modern=true)=>{for(const fn of callbacks)fn(true,modern?
  [{remote_client_id:'999',item_data:[row(99)]},{remote_client_id:'0',item_data:items}]:items);};
assert.equal((await run()).ready,false);assert.equal(callbacks.size,1);assert.equal(calls.length,0);
emit([row(10,300),row(20,100),row(30,5,0)]);
const snapshot=await run();assert.equal(snapshot.ready,true);
assert.equal(JSON.stringify(snapshot).includes('PRIVATE'),false);
assert.deepEqual(Array.from(snapshot.items,row=>row.appid),[10,20,30]);
for(const ids of [[99],[30],[10,10],[],[-1],['10']])
  await assert.rejects(run('queue',ids),/Invalid|changed/);
assert.equal(calls.length,0,'all selections validate before any queue mutation');
assert.equal((await run('queue',[10,20])).queued,2);
assert.deepEqual(calls,[['queue',20,'0'],['index',20,1,'0'],['queue',10,'0'],['index',10,2,'0'],['resume',30,'0']]);
await assert.rejects(run('queue',[10]),/awaiting a Steam update/);
calls.length=0;emit([row(10),row(20)],false);
await assert.rejects(run('queue',[10],'one',1),/Downloads changed/);
await run('queue',[10]);assert.deepEqual(calls,[['queue',10],['index',10,0],['resume',10]]);
calls.length=0;emit([row(10),row(20)],false);api.SetQueueIndex=async()=>{throw Error('Private failure');};
await assert.rejects(run('queue',[10,20]),/Queued 1 of 2 downloads; Private failure/);
assert.deepEqual(calls,[['queue',10]],'a partial failure stops later items and resume');
api.SetQueueIndex=async()=>{};calls.length=0;emit([row(10),row(20)],false);
api.QueueAppUpdate=async(...args)=>{calls.push(['queue',...args]);emit([row(10),{...row(20),completed:true}],false);};
await assert.rejects(run('queue',[10,20]),/Downloads changed during/);
assert.deepEqual(calls,[['queue',10]],'an app completed during a batch is never submitted');
calls.length=0;emit([row(10),row(20)],false);
let finish;api.QueueAppUpdate=(...args)=>{calls.push(['queue',...args]);return new Promise(resolve=>finish=resolve);};
const pending=run('queue',[10,20]);
await assert.rejects(run('queue',[20]),/in progress/);
await run('close');finish();
await assert.rejects(pending,/panel closed/);assert.equal(calls.length,1);
assert.equal(callbacks.size,0);assert.equal(intervals.size,0);
await run();emit([row(10)]);
now+=16000;for(const timer of [...intervals.values()])timer();
assert.equal(callbacks.size,0,'abandoned iframe releases its native subscription');
await run();emit(Array(2049).fill(row(10)));
await assert.rejects(run(),/limit/);await assert.rejects(run('queue',[10]),/unavailable/);
await run('close');await run();emit([{...row(10),queue_index:'-1'}]);
await assert.rejects(run(),/Invalid/);await run('close');
await run();emit([row(10)]);calls.length=0;
const hanging=run('queue',[10]);
assert.equal(methodTimers.size,1);[...methodTimers.values()][0]();
await assert.rejects(hanging,/timed out; refresh before retrying/);
await run('close');await run('read',null,'replacement');emit([row(20)]);
const retry=run('queue',[20],'replacement');
assert.equal(calls.length,1,'a replacement panel cannot overlap a timed-out native call');
await assert.rejects(retry,/in progress/);
finish();await Promise.resolve();assert.equal(calls.length,1,'a late Steam reply never continues a timed-out batch');
assert.equal(methodTimers.size,0);
await new Promise(resolve=>setImmediate(resolve));
api.QueueAppUpdate=async(...args)=>calls.push(['queue',...args]);
api.SetQueueIndex=async(...args)=>calls.push(['index',...args]);
await run('queue',[20],'replacement');
assert.deepEqual(calls.slice(1),[['queue',20,'0'],['index',20,0,'0'],['resume',20,'0']],
  'a fresh panel can submit after the timed-out native call has actually settled');
await run('close',null,'replacement');
window.SteamClient.Downloads={};await assert.rejects(run(),/unavailable/);

// The iframe exposes only the fixed batch facade, with no arbitrary Steam method.
const host=readFileSync(new URL('../../ui/framey-host.js',import.meta.url),'utf8');
const start=host.indexOf("  if (document.getElementById('framey-bundle')?.dataset?.downloads");
const block=host.slice(start,host.indexOf('  DFL.DialogButton.render',start));
const requests=[],messages=[],events=[],timers=new Map();let id=0;
const error={textContent:''},hostWindow={SteamClient:{}};
const h=vm.createContext({window:hostWindow,error,cacheSession:'test',
  document:{getElementById:()=>({dataset:{downloads:'1'}})},
  request:(method,args,_legacy,type)=>new Promise((resolve,reject)=>requests.push({method,args,type,resolve,reject})),
  parent:{postMessage:message=>messages.push(message)},addEventListener:(type,fn)=>events.push({type,fn}),
  setTimeout:fn=>{timers.set(++id,fn);return id;},clearTimeout:key=>timers.delete(key)});
vm.runInContext(block,h);
let rows;
const handle=hostWindow.SteamClient.Downloads.RegisterForDownloadItems((_initial,value)=>rows=value);
assert.equal(requests[0].type,'framey:downloads');assert.equal(requests[0].method,'read');
requests[0].resolve({ready:true,revision:1,items:[row(10)]});await new Promise(resolve=>setImmediate(resolve));
assert.equal(rows[0].remote_client_id,'0');assert.equal(rows[0].item_data[0].appid,10);
const queue=hostWindow.SteamClient.Downloads.FrameyQueueDownloads([10]);
assert.equal(requests.at(-1).method,'queue');requests.at(-1).reject(Error('Private refusal'));
assert.equal(requests.at(-1).args[1],1);
await assert.rejects(queue,/Private refusal/);
assert.equal(hostWindow.SteamClient.Downloads.QueueAppUpdate,undefined);
handle.unregister();assert.equal(messages.at(-1).type,'framey:downloads:close');assert.equal(timers.size,0);
await assert.rejects(hostWindow.SteamClient.Downloads.FrameyQueueDownloads([10]),/unavailable/);
