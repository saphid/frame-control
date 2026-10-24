const {test}=require('node:test');
const assert=require('node:assert/strict');
const {workspaceFixture,html}=require('./workspace_fixture.cjs');
function fixture() {
  const f=workspaceFixture();
  const start=html.indexOf('// ---- Read-only game storage ----');
  f.run(html.slice(start,html.indexOf('// ---- Backup and recovery kit',start)));
  const size=html.indexOf('function sizeText(');
  f.run(html.slice(size,html.indexOf('const backupKinds',size)));
  return f;
}
const sample={home:{state:'ok',total:1000,free:200,used:700},discovery:'permission-denied',libraries:[{
  path:'<img onerror=alert(1)>',capacity:{state:'missing'},state:'partial',gameBytes:10,toolBytes:0,
  recordedBytes:10,unknownSizes:1,issues:[{file:'bad.acf',state:'invalid-metadata'}],
  apps:[{appid:'1',name:'<script>bad</script>',bytes:null,kind:'game'},{appid:'2',name:'Zero',bytes:0,kind:'game'}]}]};
test('navigation reaches storage and refresh runs once per visit',()=>{
  const f=fixture();let calls=0;f.context.loadStorage=()=>calls++;
  f.navigate('#storage');assert.equal(f.activePage,'tools');assert.equal(f.el('storage').hidden,false);
  assert.equal(f.el('storage').parentNode,f.el('toolWorkspace'));assert.equal(calls,1);
});
test('unknown, shared capacity, partial discovery and untrusted names remain explicit',()=>{
  const f=fixture();f.context.sample=sample;const out=f.run('renderStorage(sample)');
  assert.match(out,/Permission denied/);assert.match(out,/Missing or disconnected/);
  assert.match(out,/Unknown/);assert.match(out,/0 bytes/);assert.match(out,/Partial inventory/);
  assert.match(out,/must not be added/);assert.match(out,/Other usage is unmeasured/);
  assert.match(out,/&lt;script&gt;/);assert.doesNotMatch(out,/<script>|<img/);
});
test('refresh clears old data, ignores earlier requests and shows offline failure',async()=>{
  const f=fixture(),pending=[];
  f.context.api=()=>new Promise((resolve,reject)=>pending.push({resolve,reject}));
  f.el('storageResult').innerHTML='old data';
  const first=f.run('loadStorage()'),second=f.run('loadStorage()');
  assert.match(f.el('storageResult').textContent,/Reading/);
  pending[1].resolve(sample);await second;
  const current=f.el('storageResult').innerHTML;
  pending[0].resolve({...sample,libraries:[]});await first;
  assert.equal(f.el('storageResult').innerHTML,current);
  const last=f.run('loadStorage()');pending[2].reject(new Error('Offline'));await last;
  assert.match(f.el('storageResult').textContent,/Storage unavailable: Offline/);
});
test('a response or error from another headset cannot update the view',async()=>{
  for(const fail of [false,true]) {
    const f=fixture();let resolve,reject;
    f.context.api=()=>new Promise((yes,no)=>{resolve=yes;reject=no;});
    const request=f.run('loadStorage()');f.context.devGen++;
    f.el('storageResult').textContent='New headset';
    fail?reject(new Error('Old headset')):resolve(sample);await request;
    assert.equal(f.el('storageResult').textContent,'New headset');assert.equal(f.el('storageResult').innerHTML,'');
  }
});
