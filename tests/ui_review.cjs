const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm');
const {workspaceFixture, html} = require('./workspace_fixture.cjs');
const store = fs.readFileSync(require.resolve('../ui/store.html'),'utf8');
const pick = (s,a,b) => s.slice(s.indexOf(a),s.indexOf(b,s.indexOf(a)));
const tick = async () => { for (let i=0;i<16;i++) await Promise.resolve(); };
function connectionFixture() {
  const f=workspaceFixture(), c=f.context;
  Object.assign(c,{URLSearchParams,Date,clearTimeout,link:{s:{phase:'connected'},device:'a',phase:'connected',rev:0},disp:{list:[],seq:0},cat:{apps:null},wi:{},devGen:1,androidSeq:0,androidPending:new Set(),titlesSeq:0,runningGames:[],runningSeq:0,volTimer:null,refreshing:null,lastImg:null,lastShot:null,
    sourceState:{jobs:new Map(),detail:null,detailRequest:0},touches:new Map(),gesture:null,padType:{blur(){},value:''},
    log(){},renderPill(){},renderConnDlg(){},renderHome(){},resetShots(){},resetClips(){},renderBanner(){},loadDevices(){},renderDevices(){},renderTests(){},viaText(){return 'test';},netLabel(){return 'test';},refresh:()=>Promise.resolve(),reloadAll(){},checkContactPrompt(){},ctrlReset(){},padShow:s=>{c.pad.state=s.state;}});
  c.window.connDevice='a';
  f.run('const UI_KEY="test";'+pick(html,'const HEADSET_FREE =','// What a panel shows'));
  f.run(pick(html,'function onConnection(s) {','// Read the event stream'));
  return f;
}
test('helper starts and status reads name the headset shown when requested',async()=>{
  const f=connectionFixture(),c=f.context,requests=[];
  c.fetch=async(path,opts)=>{requests.push({path,opts});return {ok:true,json:async()=>({state:'ready'})};};
  await f.run("api('/api/input?start=1')");
  await f.run("api('/api/touch?start=1')");
  c.window.connDevice='b';
  await f.run("api('/api/input')");
  assert.deepEqual(requests.map(r=>r.opts.headers['X-Frame-Device']),['a','a','b']);
  assert.ok(requests.every(r=>r.opts.method===undefined&&r.opts.body===undefined));
  delete c.window.connDevice; // A local iOS server has one fixed SSH route.
  await f.run("api('/api/touch?start=1')");
  assert.equal(requests[3].opts.headers['X-Frame-Device'],undefined);
});
test('a late input failure cannot replay A keystrokes on B',async()=>{
  const f=connectionFixture(),c=f.context,writes=[];let rejectA;
  Object.assign(c,{pad:{state:'ready',queue:[],sending:false},fetch:(path,opts)=>{writes.push({device:opts.headers['X-Frame-Device'],events:JSON.parse(opts.body).events});return writes.length===1?new Promise((_,reject)=>rejectA=reject):Promise.resolve({ok:true,json:async()=>({state:'ready',sent:true})});}});
  f.run(pick(html,'const isMove = e =>','function padKey('));f.run('padSend({key:"for A"})');
  f.run('onConnection({phase:"connected",device:{id:"b",name:"B"},devices_rev:1,now:0})');
  assert.equal(c.pad.state,'off');assert.equal(c.pad.queue.length,0);
  rejectA(Error('lost A'));await tick();c.pad.state='ready';f.run('padSend({key:"for B"})');await tick();
  assert.equal(writes.length,2);assert.equal(writes[1].device,'b');assert.equal(writes[1].events[0].key,'for B');
});
test('a device switch discards completed install results and the open detail',()=>{
  const f=connectionFixture(),c=f.context;
  Object.assign(c,{pad:{state:'off',queue:[]},padReset(){},sourceState:{jobs:new Map([['test:one',{done:true,result:{package:'app.on.a',game_data:true}}]]),detail:{app:{}},detailRequest:0}});
  f.el('appDetail').open=true;
  f.run('onConnection({phase:"connected",device:{id:"b",name:"B"},devices_rev:1,now:0})');
  assert.equal(c.sourceState.jobs.size,0);assert.equal(c.sourceState.detail,null);assert.equal(f.el('appDetail').open,false);
});
test('only a preview matching current diagnostics consent can be sent or copied',async()=>{
  const els=new Map(),$=id=>{if(!els.has(id))els.set(id,{checked:false,value:'',textContent:'',children:[]});return els.get(id);};let pending=[],sent;
  const c={$ ,api:(path,body)=>path==='/api/report/preview'?new Promise(resolve=>pending.push({body,resolve})):Promise.resolve({}),log(){},renderContact(){}};vm.createContext(c);
  vm.runInContext(pick(html,'const bug = {','function openBugReport()'),c);
  vm.runInContext(pick(html,'$("bugForm").onsubmit =','if (window.frameApp && window.frameApp.onReportProblem)'),c);
  $('bugForm').reportValidity=()=>true;$('bugDiag').checked=true;$('bugLogs').checked=true;
  const a=vm.runInContext('loadBugPreview()',c);$('bugLogs').checked=false;const b=vm.runInContext('loadBugPreview()',c);
  assert.doesNotMatch(vm.runInContext('bugReportText().body',c),/SECRET/);
  pending[1].resolve({text:'safe summary'});await b;pending[0].resolve({text:'SECRET SERVER LOG'});await a;
  c.api=(path,body)=>{if(path==='/api/report')sent=body;return Promise.resolve({id:'stub',message:'stub'});};
  await $('bugForm').onsubmit({preventDefault(){}});assert.equal(sent.diagnostics,'safe summary');
  $('bugDiag').checked=false;await vm.runInContext('loadBugPreview()',c);
  assert.doesNotMatch(vm.runInContext('bugReportText().body',c),/safe summary|SECRET/);
  $('bugDiag').checked=true;c.api=(path,body)=>new Promise(resolve=>pending.push({body,resolve}));
  const late=vm.runInContext('loadBugPreview()',c);$('bugDiag').checked=false;await vm.runInContext('loadBugPreview()',c);
  pending[2].resolve({text:'LATE SECRET'});await late;
  assert.doesNotMatch(vm.runInContext('bugReportText().body',c),/SECRET/);
});
test('clearing Steam search invalidates a pending query and pending country lookup',async()=>{
  const el={value:'Portal'},gm={country:'US',src:'store',store:[],storeQ:null,seq:0,shownBySource:{}};let resolve;
  const c={$:()=>el,gm,api:()=>new Promise(r=>resolve=r),renderChips(){},filterGames(){},encodeURIComponent};vm.createContext(c);
  vm.runInContext(pick(html,'async function searchStore() {','function setGameSource('),c);
  const a=vm.runInContext('searchStore()',c);el.value='';await vm.runInContext('searchStore()',c);resolve({results:[{name:'Portal'}]});await a;
  assert.equal(gm.storeQ,null);assert.equal(gm.store.length,0);
});
test('failed installed reads remain unknown or stale with retry, never successful empty',async()=>{
  const els=new Map(),$=id=>{if(!els.has(id))els.set(id,{textContent:'',innerHTML:'',setAttribute(){}});return els.get(id);};
  const st={installed:new Map(),needsData:new Set(),jobs:new Map(),view:'installed',q:'',loading:false,apps:[],page:0,installedState:'unknown',installedError:'',installedRequest:0};
  const c={$ ,st,api:async()=>{throw Error('offline');},toast(){},document:{querySelectorAll:()=>[]},PER_PAGE:8,catLabel:x=>x,esc:x=>x};vm.createContext(c);
  vm.runInContext(pick(store,'async function loadInstalled() {','async function search('),c);vm.runInContext(pick(store,'function list() {','function card('),c);vm.runInContext(pick(store,'function render(error) {','function turn('),c);
  await vm.runInContext('loadInstalled()',c);vm.runInContext('render()',c);
  assert.doesNotMatch($('content').innerHTML,/Nothing installed yet/);assert.match($('content').innerHTML,/data-retry-installed/);
  st.installed.set('app',{package:'app',label:'Cached App'});st.installedState='ready';
  c.card=()=>'<button>Cached App</button>';await vm.runInContext('loadInstalled()',c);vm.runInContext('render()',c);
  assert.match($('content').innerHTML,/Cached App/);assert.match($('content').innerHTML,/data-retry-installed/);
  c.api=async()=>({apps:[]});await vm.runInContext('loadInstalled()',c);vm.runInContext('render()',c);
  assert.match($('content').innerHTML,/Nothing installed yet/);assert.doesNotMatch($('content').innerHTML,/data-retry-installed/);
});

test('capture control discards old releases, timers and readiness on a target switch',async()=>{
  const f=connectionFixture(),c=f.context,writes=[];let rejectA;
  Object.assign(c,{ctrl:{on:true,queue:[],sending:false,state:'ready',held:new Set(['left']),keys:new Set([30]),pointers:new Map(),g:null,rel:[1,2]},desk:{panels:[{window:4}],focus:'old',shown:'old',loaded:true},cancelAnimationFrame(){},ctrlShow(){},ctrlAim:e=>e,
    pad:{queue:[],state:'off'},padReset(){},fetch:(path,opts)=>{writes.push({device:opts.headers['X-Frame-Device'],events:JSON.parse(opts.body).events});return writes.length===1?new Promise((_,reject)=>rejectA=reject):Promise.resolve({ok:true,json:async()=>({state:'ready',sent:true})});}});
  f.run(pick(html,'function ctrlReset() {','// Pointer moves:'));
  f.run('ctrlSend([{key:30,down:false}])');
  f.run('onConnection({phase:"connected",device:{id:"b",name:"B"},devices_rev:1,now:0})');
  assert.equal(c.ctrl.on,false);assert.equal(c.ctrl.state,'off');assert.equal(c.ctrl.held.size,0);assert.equal(c.desk.panels.length,0);
  rejectA(Error('lost A'));await tick();
  assert.equal(c.ctrl.queue.length,0);assert.equal(c.ctrl.retryAt,0);assert.equal(writes.length,1);
});

test('late installation completion cannot populate the new headset detail',async()=>{
  const f=workspaceFixture(),c=f.context,offer={source:'catalog',id:'one',name:'One',package:'app.one',downloadable:true};let finish,progress,refreshes=0;
  Object.assign(c,{sourceState:{jobs:new Map()},currentOffer:()=>offer,sourcePage:()=>'',loadAndroid:()=>refreshes++,
    runJob:async(_label,_key,start,update)=>{progress=update;await start();return new Promise(resolve=>finish=resolve);},api:async()=>({job:'a'})});
  f.run(pick(html,'function updateInstall() {','async function openStoreApp('));f.run(pick(html,'async function installStoreApp() {','async function changeSource('));
  const pending=f.run('installStoreApp()');await tick();
  c.devGen++;c.sourceState.jobs.clear();f.el('detailInstall').textContent='New headset';
  progress({stage:'Installing',percent:90});finish({package:'app.one',game_data:true});await pending;
  assert.equal(c.sourceState.jobs.size,0);assert.equal(f.el('detailInstall').textContent,'New headset');assert.equal(refreshes,0);
});

test('late input startup and touch poll responses cannot re-enable the old target',async()=>{
  const f=workspaceFixture(),c=f.context;let finish;
  Object.assign(c,{pad:{state:'off'},clientPreferences:{set(){}},padShow:s=>{c.pad.state=s.state;},api:()=>new Promise(resolve=>finish=resolve)});
  f.run(pick(html,'async function padStart() {','$("padOn").onclick'));
  const start=f.run('padStart()');c.devGen++;c.pad.state='off';finish({state:'ready'});await start;assert.equal(c.pad.state,'off');
  Object.assign(c,{ctrl:{on:true,state:'off'},ctrlShow(){},ctrlFlush(){throw Error('Must not flush stale input');}});
  f.run(pick(html,'async function ctrlPoll(', '$("viewer").tabIndex'));
  const poll=f.run('ctrlPoll(0)');c.devGen++;c.ctrl.on=false;finish({state:'ready'});await poll;assert.equal(c.ctrl.state,'off');
});
