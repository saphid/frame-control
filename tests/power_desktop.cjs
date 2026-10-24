const {test}=require('node:test');
const assert=require('node:assert/strict');
const {workspaceFixture,html}=require('./workspace_fixture.cjs');
function fixture() {
  const f=workspaceFixture();
  Object.assign(f.context, {clearTimeout(){},setTimeout(){},UI_KEY:'1',encodeURIComponent});
  const formats=['html','json','csv'].map(format=>Object.assign(f.el('download-'+format),{dataset:{powerFormat:format}}));
  const query=f.context.document.querySelectorAll;
  f.context.document.querySelectorAll=s=>s==='[data-power-format]'?formats:query(s);
  f.formats=formats;
  f.run(html.slice(html.indexOf('// ---- Read-only power observation ----'),html.indexOf('// ---- Read-only game storage ----')));
  return f;
}
const state={id:'abc',headset:{alias:'old-frame'},requested:12,received:3,running:true,stopped:null};
test('Tools navigation loads the report and renders accessible progress',async()=>{
  const f=fixture();let calls=0;f.context.api=async()=>{calls++;return state;};
  f.navigate('#powerReport');await new Promise(setImmediate);
  assert.equal(f.activePage,'tools');assert.equal(f.el('powerReport').hidden,false);
  assert.equal(f.el('powerReport').parentNode,f.el('toolWorkspace'));
  assert.equal(calls,1);assert.equal(f.el('powerProgress').value,3);
  assert.equal(f.el('powerStart').disabled,true);assert.equal(f.el('powerStop').disabled,false);
  assert.match(f.el('powerStatus').textContent,/Headset: old-frame.*3 of 12.*Observing/);
});
test('incomplete result preserves original identity and start becomes available',()=>{
  const f=fixture();f.context.sample={...state,running:false,stopped:'Headset switched; samples retained'};
  f.run('renderPower(sample)');
  assert.match(f.el('powerStatus').textContent,/old-frame.*Incomplete: Headset switched/);
  assert.equal(f.el('powerStart').disabled,false);assert.equal(f.el('powerStop').disabled,true);
});
test('stop submits observation identity and keeps progress visible',async()=>{
  const f=fixture(),calls=[];f.context.sample=state;f.run('renderPower(sample)');
  f.context.api=async(path,body)=>{calls.push([path,body]);return {...state,running:false,stopped:'Stopped by user'};};
  await f.el('powerStop').onclick();
  assert.equal(calls[0][0],'/api/power');assert.equal(calls[0][1].action,'stop');assert.equal(calls[0][1].id,'abc');
  assert.equal(f.el('powerProgress').value,3);assert.match(f.el('powerStatus').textContent,/Incomplete/);
});
test('old polls cannot overwrite newer report and retry explains retained samples',async()=>{
  const f=fixture(),pending=[];f.context.api=()=>new Promise((resolve,reject)=>pending.push({resolve,reject}));
  const first=f.run('loadPower()'),second=f.run('loadPower()');
  pending[1].resolve({...state,running:false,stopped:'Disconnected'});await second;
  const current=f.el('powerStatus').textContent;pending[0].resolve(state);await first;
  assert.equal(f.el('powerStatus').textContent,current);
  const next=f.run('loadPower()');pending[2].reject(new Error('Offline'));await next;
  assert.match(f.el('powerStatus').textContent,/Offline.*Received samples remain/);
});
test('start failure remains actionable and does not imply success',async()=>{
  const f=fixture();f.context.api=async()=>{throw new Error('Smoke session active');};
  await f.el('powerStart').onclick();assert.match(f.el('powerStatus').textContent,/Smoke session/);
  assert.equal(f.el('powerStart').disabled,false);
});
test('download captures observation ID, fetches an authenticated blob and names the file',async()=>{
  const f=fixture(),requests=[],saved=[];
  f.context.sample={...state,running:false,stopped:'Disconnected'};f.run('renderPower(sample)');
  f.context.fetch=async(url,opts)=>{requests.push([url,opts]);return {ok:true,blob:async()=>({report:true})};};
  f.context.URL={createObjectURL:()=> 'blob:report',revokeObjectURL(){}};
  f.context.document.createElement=()=>({click(){saved.push({href:this.href,name:this.download});}});
  await f.formats[0].onclick();
  assert.equal(requests[0][0],'/api/power/report?id=abc&format=html');
  assert.equal(requests[0][1].headers['X-Frame-UI'],'1');
  assert.deepEqual(saved,[{href:'blob:report',name:'frame-power-abc.html'}]);
  assert.match(f.el('powerSaveStatus').textContent,/Download requested/);
  f.context.fetch=async()=>({ok:false,json:async()=>({error:'Report replaced'})});
  await f.formats[0].onclick();
  assert.match(f.el('powerSaveStatus').textContent,/Download failed: Report replaced/);
  assert.equal(f.formats[0].disabled,false);
});
test('packaging guard requires shared modules and detects missing resources',()=>{
  const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
  const guard=require('../app/build/check-resources');const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'power-resources-'));
  try {
    for(const rel of guard.REQUIRED) {const file=path.join(tmp,rel);fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,'test');}
    assert.deepEqual(guard.missing(tmp),[]);
    for(const rel of ['ui/frame_power.py','ui/frame_status.py','scripts/frame_power_sample.py','scripts/frame_power_report.py']) {
      assert.ok(guard.REQUIRED.includes(rel));fs.unlinkSync(path.join(tmp,rel));assert.ok(guard.missing(tmp).includes(rel));
    }
  } finally {fs.rmSync(tmp,{recursive:true,force:true});}
});
