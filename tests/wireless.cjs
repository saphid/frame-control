const {test}=require('node:test');
const assert=require('node:assert/strict');
const {workspaceFixture,html}=require('./workspace_fixture.cjs');
function fixture() {
  const f=workspaceFixture();
  const start=html.indexOf('// ---- Read-only PC wireless doctor ----');
  f.run(html.slice(start,html.indexOf('// ---- Read-only game storage ----',start)));
  return f;
}
const sample={state:'partial',observedAt:'2026-10-24T12:00:00Z',sources:{pnp:'ok',wlan:'unavailable'},
  multipleWifiDirect:true,wifiDirectInstances:['one','two'],overlap:'unknown',devices:[{
  id:'SWD\\WIFIDIRECT\\<unsafe>',name:'<img onerror=alert(1)>',interface:'<script>bad</script>',
  wifiDirect:true,identityEvidence:'PnP enumerator',present:false,pnpStatus:'Error',problemCode:22,
  operational:null,media:null,defaultRoute:null,channel:1,band:null}]};
test('opening and revisiting the tool never starts a query',()=>{
  const f=fixture();let calls=0;f.context.api=()=>calls++;
  f.navigate('#wireless');assert.equal(f.activePage,'tools');
  assert.equal(f.el('wireless').hidden,false);assert.equal(f.el('wireless').parentNode,f.el('toolWorkspace'));
  f.navigate('#tools');f.navigate('#wireless');assert.equal(calls,0);
});
test('distinct instances, unknown states and privacy limits remain explicit and escaped',()=>{
  const f=fixture();f.context.sample=sample;const out=f.run('renderWireless(sample)');
  for(const phrase of ['2 distinct','do not prove','overlap is unknown','Unknown','(disabled)',
    'English netsh','not the Steam dongle channel','review before sharing','&lt;img','&lt;script','&lt;unsafe&gt;']) assert.ok(out.includes(phrase),phrase);
  assert.doesNotMatch(out,/<script>|<img/);
  assert.doesNotMatch(out,/disable.*button|onclick=/);
  f.context.sample={...sample,overlap:'possible'};
  assert.match(f.run('renderWireless(sample)'),/spectrum overlap.*possible; interference is unconfirmed/);
});
test('click reads once, disables repeated clicks and renders partial inventory',async()=>{
  const f=fixture();let resolve,calls=0;
  f.context.api=path=>{assert.equal(path,'/api/host/wireless');calls++;return new Promise(yes=>resolve=yes);};
  const request=f.el('wirelessRead').onclick();
  assert.equal(f.el('wirelessRead').disabled,true);assert.match(f.el('wirelessStatus').textContent,/Reading/);
  resolve(sample);await request;
  assert.equal(calls,1);assert.equal(f.el('wirelessRead').disabled,false);
  assert.match(f.el('wirelessResult').innerHTML,/distinct Wi-Fi Direct/);
  assert.match(f.el('wirelessStatus').textContent,/Partial PC snapshot/);
});
test('unsupported, busy and failed probes leave no stale inventory and allow retry',async()=>{
  for(const result of [{state:'unsupported',message:'Windows only'},{state:'busy',message:'Try again'},new Error('Denied')]) {
    const f=fixture();f.el('wirelessResult').textContent='stale inventory';
    f.context.api=async()=>{if(result instanceof Error) throw result; return result;};
    await f.el('wirelessRead').onclick();
    assert.equal(f.el('wirelessResult').textContent,'');
    assert.match(f.el('wirelessStatus').textContent,/Windows only|Try again|Denied/);
    assert.equal(f.el('wirelessRead').disabled,false);
  }
});
