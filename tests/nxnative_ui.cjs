const {test} = require('node:test');
const assert = require('node:assert/strict');
const ui = require('../ui/nxnative.js');

function page() {
  const elements = new Map();
  function get(id) {
    if (!elements.has(id)) elements.set(id, {value:'', innerHTML:'', textContent:'', disabled:false,
      open:false, close(){this.open=false;}, showModal(){this.open=true;}});
    return elements.get(id);
  }
  const fields = [{name:'location',value:'/mounted/games'}, {name:'name',value:'Mine'}];
  fields.namedItem = name => fields.find(f => f.name === name);
  get('nxnativeAdd').elements = fields;
  get('nxnativeAdd').reset = () => { fields.forEach(f => {f.value='';}); };
  const open = {};
  return {document:{getElementById:get,querySelectorAll:()=>[open]}, get, fields, open};
}

test('mount is passive; opening fetches metadata only and clarifies phone paths', async () => {
  const p=page(), calls=[];
  const controller=ui.mount({document:p.document,api:async (...args)=>{calls.push(args);return {sources:[],games:[]};},mobile:()=>true});
  assert.equal(calls.length,0);
  await controller.open();
  assert.deepEqual(calls,[['/api/nxnative']]);
  assert.equal(p.get('nxnativeDlg').open,true);
  assert.match(p.get('nxnativePathNote').textContent,/Frame, not your phone/);
});

test('untrusted metadata is escaped and raw ROMs cannot be installed', () => {
  const rows=ui.gameRows([{id:'g',source_id:'s',name:'<img src=x onerror=alert(1)>',installable:false,
    reason:'Prepare <this>'}], '', false);
  assert.match(rows,/&lt;img/);
  assert.doesNotMatch(rows,/<img/);
  assert.doesNotMatch(rows,/data-nx-install/);
  assert.match(rows,/data-nx-prepare/);
  assert.match(rows,/Preparation steps/);
  assert.equal(ui.gameRows([{name:'Dread',id:'g',source_id:'s',installable:true}], 'celeste',false).includes('No games match'),true);
  assert.match(ui.sourceRows([{id:'" onclick="bad',name:'<script>',location:'/private'}],false),/&quot; onclick=&quot;bad/);
});

test('add source waits for index job and keeps sources private to the API', async () => {
  const p=page(), calls=[];
  const controller=ui.mount({document:p.document, sleep:async()=>{}, api:async (path,body)=>{
    calls.push([path,body]);
    if(body)return {job:'index job'};
    if(path.startsWith('/api/job'))return {done:true,result:{message:'Added Mine'}};
    return {sources:[{id:'s',name:'Mine',location:'/mounted/games'}],games:[]};
  }});
  await p.get('nxnativeAdd').onsubmit({preventDefault(){}});
  assert.deepEqual(calls[0],['/api/nxnative',{action:'add',location:'/mounted/games',name:'Mine'}]);
  assert.equal(calls[1][0],'/api/job?id=index%20job');
  assert.equal(p.fields[0].value,'');
  assert.match(p.get('nxnativeSources').innerHTML,/Mine/);
  assert.equal(controller.state.busy,false);
});

test('failed addition preserves the entered location for retry', async () => {
  const p=page();
  ui.mount({document:p.document,api:async()=>{throw Error('Network share unavailable');}});
  await p.get('nxnativeAdd').onsubmit({preventDefault(){}});
  assert.equal(p.fields[0].value,'/mounted/games');
  assert.equal(p.get('nxnativeStatus').textContent,'Network share unavailable');
});

test('raw entries open the preparation guide without starting a download', async () => {
  const p=page(), calls=[];
  const controller=ui.mount({document:p.document,api:async(path,body)=>{
    calls.push([path,body]);
    return {sources:[],games:[],preparation:{title:'Prepare on Mac',steps:['Use your extracted game'],
      command:'python3 build.py --bundle <your-output>',requirements:['Matching shader inputs']}};
  }});
  await controller.open();
  assert.match(p.get('nxnativeGuide').innerHTML,/build.py --bundle &lt;your-output&gt;/);
  p.get('nxnativeGames').onclick({target:{closest:selector=>selector==='[data-nx-prepare]'?{}:null}});
  assert.equal(p.get('nxnativePreparation').open,true);
  assert.equal(calls.length,1);
});

test('LÖVE guide escapes metadata and hands prepared APKs to the existing chooser without downloading', async () => {
  const p=page(), calls=[]; let chooser=0;
  const controller=ui.mount({document:p.document,onInstallApk:()=>{
    assert.equal(p.get('nxnativeDlg').open,false);
    chooser++;
  },api:async(path,body)=>{
    calls.push([path,body]);
    return {sources:[],games:[],preparation:{title:'NxNative',steps:[],love:{
      title:'LÖVE <img src=x onerror=bad>',steps:['Use your own main.lua & assets'],
      command:'python3 frame/love/package.py --game <your-folder>',requirements:['Pinned runtime']}}};
  }});
  await controller.open();
  const guide=p.get('nxnativeGuide');
  assert.match(guide.innerHTML,/LÖVE &lt;img/);
  assert.doesNotMatch(guide.innerHTML,/<img/);
  assert.match(guide.innerHTML,/main.lua &amp; assets/);
  assert.match(guide.innerHTML,/--game &lt;your-folder&gt;/);
  assert.match(guide.innerHTML,/data-nx-install-apk/);
  guide.onclick({target:{closest:()=>null}});
  assert.equal(chooser,0);
  controller.state.busy=true;
  guide.onclick({target:{closest:()=>({})}});
  assert.equal(chooser,0);
  assert.equal(p.get('nxnativeDlg').open,true);
  controller.state.busy=false;
  guide.onclick({target:{closest:()=>({})}});
  assert.equal(chooser,1);
  assert.deepEqual(calls,[['/api/nxnative',undefined]]);
});

test('queued install follows progress, refreshes metadata and calls installed only on success', async () => {
  const p=page(); let polls=0, installed=0;
  const controller=ui.mount({document:p.document,sleep:async()=>{},onInstalled:()=>installed++,api:async(path,body)=>{
    if(body)return {job:'j'};
    if(path.startsWith('/api/job'))return ++polls===1 ? {stage:'Copying verified files',done:false} : {done:true,result:{message:'Installed game'}};
    return {sources:[],games:[]};
  }});
  assert.equal(await controller.action({action:'install',source:'s',id:'g'},'Install'),true);
  assert.equal(polls,2);assert.equal(installed,1);
  assert.equal(p.get('nxnativeStatus').textContent,'Installed game');
  const fail=ui.mount({document:p.document,onInstalled:()=>installed++,api:async(path,body)=>body?{job:'bad'}:{done:true,error:'Checksum mismatch'}});
  assert.equal(await fail.action({action:'install',source:'s',id:'g'},'Install'),false);
  assert.equal(installed,1);
  assert.equal(p.get('nxnativeStatus').textContent,'Checksum mismatch');
});
