const test=require('node:test');
const assert=require('node:assert/strict');
const {workspaceFixture,html}=require('./workspace_fixture.cjs');
const deferred=()=>{let resolve,reject;const promise=new Promise((ok,bad)=>{resolve=ok;reject=bad;});return {promise,resolve,reject};};
function installFixture() {
  const f=workspaceFixture();
  Object.assign(f.context,{wi:{queue:[]},wiNext(){f.calls.push(['review']);},sendFiles:files=>f.calls.push(['files',files])});
  const start=html.indexOf('function openInstallChooser()'),end=html.indexOf('function renderHome(',start);
  f.run(html.slice(start,end));return f;
}
test('Add / Install retains cancellation and hands chosen files to the existing transfer flow',()=>{
  const f=installFixture(),input=f.el('installFileInput');let clicks=0;
  input.click=()=>clicks++;f.run('openInstallChooser()');f.el('installChooseFile').onclick();assert.equal(clicks,1);
  input.files=[];input.onchange();assert.equal(f.el('installChooser').open,true);assert.equal(f.calls.length,0);
  const files=[{name:'game.zip'},{name:'player.apk'}];input.files=files;input.value='chosen';input.onchange();
  assert.equal(f.el('installChooser').open,false);assert.equal(f.context.location.hash,'#transfer');assert.equal(input.value,'');
  assert.deepEqual(Array.from(f.calls[0][1]),files);
});
test('chooser destinations reapply explicit views when their hash is already active',()=>{
  const cases=[['#appStore',"selectApps('installed')",f=>assert.equal(f.el('appStore').hidden,false)],
    ['#linuxApps',"selectApps('browse')",f=>assert.equal(f.el('appsLinux').hidden,false)],
    ['#getgames',"selectLibrary('all','installed')",f=>assert.equal(f.context.gm.src,'owned')],
    ['#steamStore',"selectLibrary('all','owned')",f=>assert.equal(f.context.gm.src,'store')]];
  for(const [hash,change,verify] of cases){
    const f=installFixture();f.navigate(hash);f.run(change);f.run('openInstallChooser()');let prevented=false;
    f.el('installChooser').onclick({target:{closest:()=>({getAttribute:()=>hash})},preventDefault(){prevented=true;}});
    assert.equal(prevented,true,hash);assert.equal(f.el('installChooser').open,false);verify(f);
  }
});
test('download links accept supported direct and manifest forms and reject malformed handoffs',()=>{
  const f=installFixture();
  for(const [raw,expected] of [
    [' https://example.com/game.zip ',{kind:'url',target:'https://example.com/game.zip'}],
    ['frame-control://install?url=https%3A%2F%2Fexample.com%2Fapp.apk',{kind:'url',target:'https://example.com/app.apk'}],
    ['frame-control://install?manifest=https%3A%2F%2Fexample.com%2Fgame.json',{kind:'manifest',target:'https://example.com/game.json'}]
  ]){f.context.raw=raw;assert.deepEqual(JSON.parse(JSON.stringify(f.run('installLinkRequest(raw)'))),expected);}
  for(const raw of ['file:///tmp/app.apk','javascript:alert(1)','https://user:secret@example.com/a.apk',
    'frame-control://other?url=https://example.com/a.apk','frame-control://install/path?url=https://example.com/a.apk',
    'frame-control://install?url=https://example.com/a.apk&manifest=https://example.com/a.json',
    'frame-control://install?url=https://example.com/a.apk&url=https://example.com/b.apk',
    'frame-control://install?manifest=garbage','not a URL','https://example.com/'+ 'x'.repeat(2050)]){
    f.context.raw=raw;assert.throws(()=>f.run('installLinkRequest(raw)'));
  }
});
test('link form queues a review only, with inline errors and a bounded waiting queue',()=>{
  const f=installFixture(),submit=()=>f.el('installLinkForm').onsubmit({preventDefault(){}});
  f.run('openInstallChooser()');f.el('installUrl').value='invalid';submit();
  assert.equal(f.el('installChooser').open,true);assert.equal(f.el('installLinkError').hidden,false);assert.equal(f.context.wi.queue.length,0);assert.equal(f.calls.length,0);
  f.el('installUrl').value='https://example.com/game.zip';submit();
  assert.equal(f.el('installChooser').open,false);assert.equal(f.context.wi.queue.length,1);assert.deepEqual(f.calls,[['review']]);
  f.context.wi.queue=Array(5).fill({kind:'url',target:'https://example.com/game.zip'});f.run('openInstallChooser()');submit();
  assert.equal(f.el('installChooser').open,true);assert.equal(f.context.wi.queue.length,5);assert.match(f.el('installLinkError').textContent,/Finish or close/);
});
test('link review checks metadata but starts no download before the existing confirmation',async()=>{
  const f=installFixture(),writes=[];
  Object.assign(f.context,{log(){},gb:n=>String(n),api:async(path,body)=>{writes.push({path,body});return {id:'plan-1',name:'Game',host:'example.com',linkHost:'example.com',file:'game.zip',kindLabel:'PC game',size:100};}});
  f.el('wiGo').focus=()=>{};f.el('wiDlg').addEventListener=()=>{};
  const start=html.indexOf('const wi ='),end=html.indexOf('async function wiPoll(',start);f.run(html.slice(start,end));
  f.run("wi.queue.push({kind:'url',target:'https://example.com/game.zip'})");await f.run('wiNext()');
  assert.equal(writes.length,1);assert.equal(writes[0].path,'/api/webinstall/check');assert.equal(f.el('wiDlg').open,true);assert.equal(f.el('wiGo').disabled,false);
  const cancel=html.indexOf('$("wiCancel").onclick = async () =>');f.run(html.slice(cancel,html.indexOf('// Escape',cancel)));
  await f.el('wiCancel').onclick();assert.equal(f.el('wiDlg').open,false);assert.equal(writes.length,1);
});
test('catalog installs retain progress, failure retry and installed-app handoff',async()=>{
  const f=workspaceFixture(),offer={source:'fdroid',id:'org.player',package:'org.player',name:'Player',downloadable:true,version_code:42},writes=[];
  let success=false,refreshes=0,opened;
  Object.assign(f.context,{sourceState:{jobs:new Map()},currentOffer:()=>offer,sourcePage:()=>'',openInstalledApp:pkg=>opened=pkg,
    api:async(path,body)=>{writes.push({path,body});return {job:'job-1'};},loadAndroid:()=>refreshes++,
    runJob:async(label,key,start,progress)=>{await start();progress({stage:'Installing',percent:75});assert.equal(f.el('detailProgress').value,75);return success?{package:'org.player'}:undefined;}});
  const start=html.indexOf('function updateInstall()'),end=html.indexOf('async function openStoreApp(',start);f.run(html.slice(start,end));
  const install=html.indexOf('async function installStoreApp()');f.run(html.slice(install,html.indexOf('async function changeSource(',install)));
  await f.run('installStoreApp()');assert.equal(f.el('detailInstall').textContent,'Try again');assert.match(f.el('detailInstallNote').textContent,/couldn't finish/);
  success=true;await f.run('installStoreApp()');assert.equal(f.el('detailInstall').textContent,'Open in Steam');assert.equal(refreshes,1);
  assert.equal(writes.length,2);assert.deepEqual(JSON.parse(JSON.stringify(writes[0])),{path:'/api/sources/install',body:{source:'fdroid',id:'org.player',version_code:42}});
  f.context.sourceState.jobs.clear();f.context.androidApps=[{package:'org.player'}];f.el('appDetail').showModal();f.run('updateInstall()');
  assert.equal(f.el('detailInstall').textContent,'View installed app');await f.run('installStoreApp()');assert.equal(opened,'org.player');assert.equal(writes.length,2);assert.equal(f.el('appDetail').open,false);
});
test('Steam actions distinguish owned installation, installed play and non-owned store handoff',()=>{
  const f=workspaceFixture();
  f.context.gm.byId=new Map([[1,{installed:false}],[2,{installed:true}]]);
  const start=html.indexOf('function gameButtons(');f.run(html.slice(start,html.indexOf('function moreGames(',start)));
  assert.match(f.run("gameButtons(1,'Owned',false)"),/data-gm="install"/);
  assert.match(f.run("gameButtons(2,'Installed',false)"),/data-launch="2"/);
  for(const free of [false,true]){const output=f.run(`gameButtons(3,'Store',${free})`);assert.match(output,free?/Get on Steam/:/Buy on Steam/);assert.doesNotMatch(output,/data-gm="install"/);}
  f.context.gm.dl={appid:1,percent:30};assert.match(f.run("gameButtons(1,'Owned',false)"),/Downloading 30%/);
});
test('Apps Games Tools Settings expose installed, browse, ownership and intentional legacy routes',()=>{
  const f=workspaceFixture();
  assert.deepEqual(f.links.map(a=>a.getAttribute()),['#apps','#games','#tools','#settings']);
  f.navigate('');assert.equal(f.activePage,'apps');assert.equal(f.el('androidLibrary').hidden,false);assert.equal(f.el('appStore').hidden,true);
  f.navigate('#games');assert.equal(f.activePage,'games');assert.equal(f.el('getgames').hidden,true);assert.equal(f.el('library').hidden,false);assert.equal(f.el('sideloaded').hidden,false);
  f.navigate('#getgames');assert.equal(f.el('getgames').hidden,false);assert.equal(f.el('library').hidden,true);assert.equal(f.context.gm.src,'owned');
  f.navigate('#steamStore');assert.equal(f.context.gm.src,'store');assert.equal(f.el('getgames').hidden,false);
  f.navigate('#appStore');assert.equal(f.activePage,'apps');assert.equal(f.el('appStore').hidden,false);assert.equal(f.el('androidLibrary').hidden,true);
  f.navigate('#linuxApps');assert.equal(f.activePage,'apps');assert.equal(f.el('appsLinux').hidden,false);
  f.navigate('#androidLibrary');assert.equal(f.el('appsLinux').hidden,true);assert.equal(f.el('androidLibrary').hidden,false);
  f.navigate('#display');assert.equal(f.activePage,'settings');assert.equal(f.el('androidSettings').hidden,false);assert.equal(f.el('settingsDirectory').hidden,true);
  f.navigate('#settings');assert.equal(f.el('settingsDirectory').hidden,false);assert.equal(f.el('settingsWorkspace').hidden,true);
  for(const [route,page,primary] of [['#devices','devices','settings'],['#control','control','settings'],['#shots','capture','tools'],['#view','capture','tools'],['#pad','tools','tools'],['#comfort','tools','tools'],['#library','games','games'],['#discover','apps','apps'],['#privacy','settings','settings']]){
    f.navigate(route);assert.equal(f.activePage,page,route);assert.equal(f.run('primaryPage(page)'),primary,route);
  }
});
test('app views and game scopes restore separate scroll positions, queries and filters',()=>{
  const f=workspaceFixture();f.navigate('#appStore');f.el('sourceQ').value='video';f.scroll(480);
  f.run("selectApps('installed')");f.el('libQ').value='player';f.scroll(220);
  f.navigate('#games');f.scroll(160);f.navigate('#apps');assert.equal(f.context.window.scrollY,220);
  f.run("selectApps('browse')");assert.equal(f.context.window.scrollY,480);assert.equal(f.el('sourceQ').value,'video');assert.equal(f.el('libQ').value,'player');
  f.navigate('#games');assert.equal(f.context.window.scrollY,160);
  f.run("selectLibrary('steam')");f.scroll(600);f.run("selectLibrary('sideloaded')");f.scroll(80);f.run("selectLibrary('steam')");assert.equal(f.context.window.scrollY,600);
  f.context.location.hash='#apps';f.scroll(0);f.run('showPage()');f.navigate('#games');assert.equal(f.context.window.scrollY,600);
});
test('Android browse opens Apps Browse after visiting the Steam store',()=>{
  const f=workspaceFixture();f.navigate('#steamStore');f.navigate('#androidLibrary');
  const start=html.indexOf('function showAndroidTab(tab)'),end=html.indexOf("document.querySelectorAll('[data-store-tab]')",start);
  f.run(html.slice(start,end));f.run("showAndroidTab('browse')");f.run('showPage()');
  assert.equal(f.activePage,'apps');assert.equal(f.el('appStore').hidden,false);
});
test('empty installed library opens Browse even when its route is already in the address bar',()=>{
  const f=workspaceFixture();let click;
  f.context.libState={q:'',filter:'all'};f.el('andApps').addEventListener=(name,fn)=>click=fn;
  const helper=html.indexOf('function showAndroidTab(tab)');
  f.run(html.slice(helper,html.indexOf("document.querySelectorAll('[data-store-tab]')",helper)));
  const start=html.indexOf('function renderLibrary()');
  f.run(html.slice(start,html.indexOf('document.addEventListener("click",',start)));
  f.navigate('#appStore');f.run("selectApps('installed');renderLibrary()");
  assert.match(f.el('andApps').innerHTML,/data-store-go="browse"/);assert.equal(f.el('appStore').hidden,true);
  click({target:{closest:()=>({dataset:{storeGo:'browse'}})}});
  assert.equal(f.context.location.hash,'#appStore');assert.equal(f.el('appStore').hidden,false);assert.equal(f.el('appsInstalled').hidden,true);
});
test('owned scope excludes installed games and keeps unknown compatibility visible',()=>{
  const f=workspaceFixture(),gm=f.context.gm;
  Object.assign(gm,{owned:[{id:1,installed:true,name:'Installed',frame:3,sort:'installed'},{id:2,installed:false,name:'Owned unknown',frame:0,sort:'owned',lastPlayed:0}],q:'',filters:{owned:new Set(['0','1','2','3'])},shown:0});
  f.context.moreGames=()=>{};
  const start=html.indexOf('function filterGames('),end=html.indexOf('function price(',start);
  f.run(html.slice(start,end));f.run('filterGames()');
  assert.deepEqual(Array.from(gm.results,g=>g.id),[2]);
});
test('installed load succeeds while optional catalog is unresolved, and errors keep local retry',async()=>{
  const f=workspaceFixture(),pending=deferred();
  let result={apps:[{package:'org.example.player',label:'Player',running:false}]},fail=false;
  f.context.api=path=>path==='/api/android'?fail?Promise.reject(Error('Temporary network failure')):Promise.resolve(result):pending.promise;
  f.context.renderLibrary=()=>f.el('andApps').innerHTML='installed';
  f.run('let androidSeq=0; const androidPending=new Set(); let installedPackage=null;');
  const start=html.indexOf('async function loadAndroid() {'),end=html.indexOf("$('androidRetry').onclick",start);
  f.run(html.slice(start,end));await f.run('loadAndroid()');
  assert.equal(f.el('andApps').innerHTML,'installed');assert.equal(f.el('androidLoadError').hidden,true);
  fail=true;await f.run('loadAndroid()');assert.equal(f.el('andApps').innerHTML,'installed');assert.equal(f.el('androidLoadError').hidden,false);
  assert.match(f.el('androidLoadMessage').textContent,/Temporary network failure/);
  fail=false;await f.run('loadAndroid()');assert.equal(f.el('androidLoadError').hidden,true);
  assert.ok(html.includes('loadAndroid();\n\n// ---- Android display'),'startup must not wait for catalog completion');
});
test('older installed responses cannot replace a newer read',async()=>{
  const f=workspaceFixture(),old=deferred(),next=deferred();let calls=0;
  f.context.api=()=>++calls===1?old.promise:next.promise;f.context.renderLibrary=()=>{};
  f.run('let androidSeq=0;const androidPending=new Set();let installedPackage=null;');
  const start=html.indexOf('async function loadAndroid() {'),end=html.indexOf("$('androidRetry').onclick",start);
  f.run(html.slice(start,end));const a=f.run('loadAndroid()'),b=f.run('loadAndroid()');
  next.resolve({apps:[{package:'new'}]});await b;old.resolve({apps:[{package:'old'}]});await a;
  assert.equal(f.context.androidApps[0].package,'new');
});
test('Android Open dispatch is deduplicated while pending and returns to an enabled row',async()=>{
  const f=workspaceFixture(),request=deferred(),writes=[];
  Object.assign(f.context,{devGen:1,installing:new Set(),toast(){},act:async(label,work)=>work(),
    api:(path,body)=>{writes.push({path,body});return request.promise;},loadAndroid:async()=>{},renderLibrary(){},cat:{apps:null},loadReports(){}});
  f.run('const androidPending=new Set();let installedPackage=null;');
  const start=html.indexOf('document.body.addEventListener("click", async e => {',html.indexOf('$("catChips").onclick'));
  const end=html.indexOf('loadAndroid();\n\n// ---- Android display',start);
  f.run(html.slice(start,end));
  const button={dataset:{and:'launch',pkg:'org.example.player',name:'Player'},disabled:false,textContent:'Open'};
  const event={target:{closest:()=>button}};
  const a=f.listeners['body-click'](event);await f.listeners['body-click'](event);
  assert.equal(button.disabled,true);assert.equal(button.textContent,'Wait…');assert.equal(button.ariaBusy,'true');assert.equal(writes.length,1);
  assert.deepEqual(JSON.parse(JSON.stringify(writes[0])),{path:'/api/android',body:{action:'launch',package:'org.example.player'}});
  request.resolve({message:'Opened'});await a;assert.equal(button.disabled,false);assert.equal(button.textContent,'Open');assert.equal(button.ariaBusy,'false');
});
test('entering Apps Installed refreshes data without clearing cached rows',()=>{
  const f=workspaceFixture();f.el('andApps').innerHTML='cached installed apps';f.navigate('#games');f.navigate('#apps');
  assert.equal(f.calls.filter(c=>c[0]==='android').length,1);
  f.run("selectApps('installed')");assert.equal(f.calls.filter(c=>c[0]==='android').length,2);
  f.navigate('#settings');f.navigate('#apps');assert.equal(f.calls.filter(c=>c[0]==='android').length,3);
  assert.equal(f.el('andApps').innerHTML,'cached installed apps');
});
test('actions from detail synchronize existing rows and stay pending through the follow-up read',async()=>{
  for(const action of ['launch','stop']) {
    const f=workspaceFixture(),request=deferred(),refresh=deferred();let writes=0,renders=0;
    const makeButton=pkg=>({dataset:{and:action,pkg,name:'Player'},disabled:false,textContent:action==='stop'?'Stop':'Open'});
    const detail=makeButton('org.example.player'),row=makeButton('org.example.player'),other=makeButton('org.other');
    const originalQuery=f.context.document.querySelectorAll;
    f.context.document.querySelectorAll=selector=>selector==='[data-and="launch"], [data-and="stop"]'?[row,detail,other]:originalQuery(selector);
    Object.assign(f.context,{devGen:1,installing:new Set(),log(){},toast(){},api:()=>{writes++;return request.promise;},
      loadAndroid:()=>refresh.promise,renderLibrary(){renders++;row.disabled=false;row.textContent=action==='stop'?'Stop':'Open';row.ariaBusy='false';},cat:{apps:null},loadReports(){}});
    f.run('const androidPending=new Set();let installedPackage=null;');
    f.run(html.slice(html.indexOf('async function act('),html.indexOf('\nfunction setConn(')));
    const start=html.indexOf('document.body.addEventListener("click", async e => {',html.indexOf('$("catChips").onclick'));
    f.run(html.slice(start,html.indexOf('loadAndroid();\n\n// ---- Android display',start)));
    f.el('installedDetail').showModal();const pending=f.listeners['body-click']({target:{closest:()=>detail}});f.el('installedDetail').close();
    for(const button of [row,detail]){assert.equal(button.disabled,true);assert.equal(button.textContent,'Wait…');assert.equal(button.ariaBusy,'true');}
    assert.equal(other.disabled,false);await f.listeners['body-click']({target:{closest:()=>row}});assert.equal(writes,1);
    request.resolve({message:'Done'});await new Promise(resolve=>setImmediate(resolve));
    assert.equal(row.disabled,true);assert.equal(detail.disabled,true);assert.equal(renders,0,'stay pending while refreshed app state is unresolved');
    refresh.resolve();await pending;assert.equal(renders,1);assert.equal(row.disabled,false);assert.equal(detail.disabled,false);assert.equal(f.run('androidPending.size'),0);
  }
});
test('regenerated Android rows and details keep the compact accessible pending state',()=>{
  const f=workspaceFixture(),app={package:'org.example.player',label:'Player',running:false};
  Object.assign(f.context,{androidApps:[app],storeIcon:()=>'<span>icon</span>'});
  f.run("const androidPending=new Set(['org.example.player']);let installedPackage=null;");
  const start=html.indexOf('function libCard(a)'),end=html.indexOf('function renderLibrary()',start);f.run(html.slice(start,end));
  for(const running of [false,true]) {
    app.running=running;const row=f.run('libCard(androidApps[0])');f.run("openInstalledApp('org.example.player')");
    assert.match(row,/disabled aria-busy="true">Wait…<\/button>/);
    assert.match(f.el('installedDetailBody').innerHTML,/disabled aria-busy="true">Wait…<\/button>/);
  }
  f.run('androidPending.clear()');const row=f.run('libCard(androidApps[0])');assert.doesNotMatch(row,/aria-busy="true"/);assert.match(row,/>Stop<\/button>/);
});
test('explicit Capture section links take priority over saved destination scroll',()=>{
  const f=workspaceFixture();f.navigate('#capture');f.scroll(700);f.calls.length=0;
  f.navigate('#shots');assert.ok(f.calls.some(c=>c[0]==='section'&&c[1]==='shots'));
  f.calls.length=0;f.navigate('#view');assert.ok(f.calls.some(c=>c[0]==='section'&&c[1]==='view'));
  f.calls.length=0;f.navigate('#view');assert.ok(f.calls.some(c=>c[0]==='section'&&c[1]==='view'));
});
test('viewer keyboard shortcuts act only in the Capture workspace',()=>{
  const f=workspaceFixture(),events=[];let handler;
  f.context.document.activeElement={tagName:'BODY'};
  f.context.document.addEventListener=(name,callback)=>handler=callback;
  Object.assign(f.context,{ctrl:{on:false},zoom:1,setZoom:n=>events.push(['zoom',n])});
  f.el('ctrlBtn').click=()=>events.push(['control']);f.el('fullBtn').click=()=>events.push(['fullscreen']);
  const start=html.indexOf('document.addEventListener("keydown", e => {',html.indexOf('$("canvas").addEventListener("pointerdown"'));
  const end=html.indexOf('\n});',start)+4;f.run(html.slice(start,end));
  f.navigate('#capture');handler({key:'+'});handler({key:'c'});handler({key:'f'});assert.equal(events.length,3);
  f.navigate('#home');handler({key:'+'});handler({key:'c'});handler({key:'f'});assert.equal(events.length,3);
});
test('late Mac streaming responses cannot reveal a different tool panel',async()=>{
  for(const rejects of [false,true]) {
    const f=workspaceFixture(),response=deferred();
    Object.assign(f.context,{api:()=>response.promise,clearTimeout(){},setTimeout(){},failed(){}});
    f.run('let mvSeq=0,mvTimer=0;');
    const start=html.indexOf('async function loadMacView(restart)'),end=html.indexOf('$("mvRefresh").onclick',start);
    f.run(html.slice(start,end));f.context.location.hash='#macview';const pending=f.run('loadMacView()');
    f.navigate('#transfer');assert.equal(f.el('macview').hidden,true);
    rejects?response.reject(Error('Network failed')):response.resolve({available:true,streams:[],displays:[],windows:[]});
    await pending;assert.equal(f.el('macview').hidden,true);assert.equal(f.el('transfer').hidden,false);
  }
});
test('Home task count includes the current Steam download',()=>{
  const f=workspaceFixture();Object.assign(f.context,{state:{hostname:'Frame',battery:{percent:80}},stateRead:{valid:true},online:true});
  f.context.gm.dl={appid:1,percent:42};f.run('renderHome()');
  assert.equal(f.el('homeJobs').textContent,'1 task in progress');assert.match(f.el('homeDownload').textContent,/42%/);
});
test('a late screenshot read cannot replace newer navigation or clear a newer viewer request',async()=>{
  const f=workspaceFixture(),old=deferred(),newer=deferred();let reads=0;
  Object.assign(f.context,{shotBlob:()=>++reads===1?old.promise:newer.promise,URL:{createObjectURL:()=> 'blob:shot',revokeObjectURL(){}},
    Image:class{set src(value){this.onload();}},draw(){},shotApp:()=> 'Game',toast(){},desk:{shown:null}});
  const start=html.indexOf('async function openShot(s)'),end=html.indexOf('async function saveShots(',start);
  f.run(html.slice(start,end));f.navigate('#capture');const pending=f.run("openShot({id:1,file:'one.png',time:1})");
  assert.equal(f.el('viewer').classList.contains('busy'),true);
  f.navigate('#library');f.scroll(240);assert.equal(f.el('viewer').classList.contains('busy'),false);
  old.resolve({});await pending;assert.equal(f.activePage,'games');assert.equal(f.context.location.hash,'#library');assert.equal(f.context.window.scrollY,240);
  f.navigate('#capture');const first=f.run("openShot({id:2,file:'two.png',time:1})");
  f.navigate('#home');f.navigate('#capture');f.run('viewGen++');f.el('viewer').classList.toggle('busy',true);
  newer.resolve({});await first;assert.equal(f.activePage,'capture');assert.equal(f.context.location.hash,'#capture');assert.equal(f.el('viewer').classList.contains('busy'),true);
});
test('Steam discovery preserves an unsubmitted query across a source change',()=>{
  const f=workspaceFixture();Object.assign(f.context.gm,{src:'store',q:'owned query',storeDraft:'',storeQ:'submitted query'});
  f.context.renderChips=()=>{};f.context.filterGames=()=>{};
  const start=html.indexOf('function setGameSource(src)'),end=html.indexOf('$("gmSrc").onclick',start);
  f.run(html.slice(start,end));f.el('gmQ').value='unsubmitted search';f.run("setGameSource('owned')");
  assert.equal(f.el('gmQ').value,'owned query');f.run("setGameSource('store')");assert.equal(f.el('gmQ').value,'unsubmitted search');
});
test('expanded owned and store results survive source and destination returns',async()=>{
  const f=workspaceFixture(),gm=f.context.gm;
  const games=Array.from({length:120},(_,i)=>({id:i+1,name:'Game '+String(i+1).padStart(3,'0'),sort:String(i).padStart(3,'0'),frame:3,installed:false,lastPlayed:0}));
  Object.assign(gm,{owned:games,store:games,storeQ:'game',storeDraft:'game',country:'US',q:'',results:[],filters:{owned:new Set(['3']),store:new Set(['3'])},seq:0});
  Object.assign(f.context,{FLABEL:{3:'Verified'},FCLASS:{3:'verified'},CDN:'https://example.invalid',renderChips(){}});
  f.el('gmGrid').insertAdjacentHTML=(position,s)=>f.el('gmGrid').innerHTML+=s;
  const start=html.indexOf('function filterGames('),end=html.indexOf('$("gmSrc").onclick',start);
  f.run(html.slice(start,end));
  f.navigate('#getgames');f.run('filterGames();moreGames()');f.scroll(7000);
  assert.equal(gm.shown,96);assert.match(f.el('gmGrid').innerHTML,/Game 096/);
  f.navigate('#steamStore');f.run('moreGames()');f.scroll(6500);
  assert.equal(gm.shown,96);f.navigate('#getgames');assert.equal(gm.shown,96);assert.match(f.el('gmGrid').innerHTML,/Game 096/);assert.equal(f.context.window.scrollY,7000);
  f.navigate('#steamStore');assert.equal(gm.shown,96);assert.match(f.el('gmGrid').innerHTML,/Game 096/);assert.equal(f.context.window.scrollY,6500);
  f.run('filterGames()');assert.equal(gm.shown,48,'a deliberate filter change resets expansion');
  const response=deferred();f.context.api=()=>response.promise;f.el('gmQ').value='new search';const search=f.run('searchStore()');
  f.navigate('#getgames');const ownedMarkup=f.el('gmGrid').innerHTML;
  response.resolve({results:games.slice(0,60)});await search;
  assert.equal(f.el('gmGrid').innerHTML,ownedMarkup,'a late store response leaves current owned results intact');
  f.navigate('#steamStore');assert.equal(gm.shown,48);assert.equal(gm.storeQ,'new search');
});
test('Home shortcuts show their tool before focusing it, so typing works on the first tap',()=>{
  const f=workspaceFixture(),pad={state:'on'},buttons=[{dataset:{go:'pad'}}];let focusedVisible=null;
  f.context.document.querySelectorAll=(q=>s=>s==='[data-go]'?buttons:q(s))(f.context.document.querySelectorAll);
  Object.assign(f.context,{pad,padStart(){},history:{pushState(_,__,url){f.context.location.hash=url;}}});
  f.el('padType').focus=()=>{focusedVisible=f.activePage==='tools'&&!f.el('pad').hidden;};
  f.navigate('#home');
  const start=html.indexOf('document.querySelectorAll("[data-go]")'),end=html.indexOf('$("nowSend").onclick',start);
  let shows=0;f.run('const realShowPage=showPage;');f.context.showPage=()=>{shows++;f.run('realShowPage()');};
  f.run(html.slice(start,end).replace(/showPage\(\)/g,'globalThis.showPage()'));buttons[0].onclick();
  assert.equal(focusedVisible,true);assert.equal(shows,1);assert.equal(f.context.location.hash,'#pad');
});
