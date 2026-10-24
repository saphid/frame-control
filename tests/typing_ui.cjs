// Type on the headset: where people find it, the T key, and copying the headset's clipboard.
// Production page code with only browser and transport boundaries replaced; no headset.
const test=require('node:test');
const assert=require('node:assert/strict');
const cc=require('../ui/control-center.js');
const {workspaceFixture,html}=require('./workspace_fixture.cjs');

const between=(from,to)=>{const start=html.indexOf(from),end=html.indexOf(to,start);assert.ok(start>=0&&end>start,from);return html.slice(start,end);};
const section=id=>between(`id="${id}"`,'</section>');

test('Home, the Right now card and the Tools directory all name it Type on the headset',()=>{
  const home=between('data-page="home"','data-page="capture"');
  assert.match(home,/<a href="#pad" title="Type on the headset \(T\)"><span>Type on the headset<\/span><small>Keyboard, trackpad and clipboard<\/small>/);
  assert.match(home,/<button data-go="pad" title="Type on the headset \(T\)">Type on the headset<\/button>/);
  assert.match(between('id="toolDirectory"','<h2>Your Frame</h2>'),/href="#pad"[^>]*><span>Type on the headset<\/span>/);
  assert.doesNotMatch(html,/Keyboard &(amp;)? trackpad<\/span>|Type on the Frame</);
});
test('the clipboard, both ways, lives beside the keyboard, not in Send to Frame',()=>{
  const pad=section('pad');
  for(const id of ['clipText','clipSend','clipMac','clipFrom'])assert.match(pad,new RegExp(`id="${id}"`),id);
  assert.match(pad,/Text only, up to 1 MB/);
  const transfer=section('transfer');
  assert.doesNotMatch(transfer,/id="clip/);
  assert.match(transfer,/<a href="#pad">Type on the headset<\/a>/);
});
test('the tool page is titled Type on the headset',()=>{
  const f=workspaceFixture();
  f.navigate('#pad');
  assert.equal(f.activePage,'tools');assert.equal(f.el('pad').hidden,false);
  assert.equal(f.el('toolTitle').textContent,'Type on the headset');
  assert.equal(f.el('transfer').hidden,true);
});

function keyFixture() {
  const f=workspaceFixture(),keys=[];let focused=0,started=0;
  Object.assign(f.context,{pad:{state:'off'},padStart(){started++;},ctrl:{on:false},PAGES:['apps','games','tools','settings'],
    history:{pushState(_,__,url){f.context.location.hash=url;}}});
  f.context.document.addEventListener=(type,fn)=>{if(type==='keydown')keys.push(fn);};
  f.context.document.querySelector=()=>null;
  f.context.document.activeElement={tagName:'BODY'};
  f.el('padType').focus=()=>{focused++;};
  f.run(between('function showNow(','$("nowSend").onclick'));
  f.run(between('document.addEventListener("keydown", e => {\n  if (e.metaKey || e.ctrlKey || e.altKey','// ---- after an APK install'));
  const press=(key,extra={})=>{let prevented=false;keys.forEach(fn=>fn({key,preventDefault(){prevented=true;},...extra}));return prevented;};
  return {f,press,get focused(){return focused;},get started(){return started;}};
}
test('T opens Type on the headset, turns the keyboard on and puts the cursor in its field',()=>{
  const k=keyFixture();
  k.f.navigate('#games');
  assert.equal(k.press('t'),true,'the T must not also be typed into the field it focuses');
  assert.equal(k.f.context.location.hash,'#pad');assert.equal(k.f.activePage,'tools');
  assert.equal(k.started,1);assert.equal(k.focused,1);
  k.f.context.pad.state='ready';k.press('T');assert.equal(k.started,1,'already on: not started again');
});
test('T stays out of the way of typing, shortcuts and keys going to the Frame',()=>{
  const k=keyFixture();
  k.f.navigate('#games');
  k.press('t',{metaKey:true});k.press('t',{ctrlKey:true});k.press('t',{altKey:true});
  k.f.context.document.activeElement={tagName:'INPUT'};k.press('t');
  k.f.context.document.activeElement={tagName:'BODY'};k.f.context.document.querySelector=s=>s==='dialog[open]'?{}:null;k.press('t');
  k.f.context.document.querySelector=()=>null;
  k.f.context.ctrl.on=true;k.f.context.document.activeElement=k.f.el('viewer');k.press('t');
  assert.equal(k.f.context.location.hash,'#games');assert.equal(k.started,0);
  k.f.context.document.activeElement={tagName:'BODY'};k.press('3');assert.equal(k.f.context.location.hash,'#tools','number keys still switch pages');
});
test('Home’s button goes through the same path, showing the tool once before focusing it',()=>{
  const f=workspaceFixture(),buttons=[{dataset:{go:'pad'}},{dataset:{go:'media'}}];let focusedVisible=null;
  f.context.document.querySelectorAll=(q=>s=>s==='[data-go]'?buttons:q(s))(f.context.document.querySelectorAll);
  Object.assign(f.context,{pad:{state:'error'},padStart(){f.calls.push(['padStart']);},history:{pushState(_,__,url){f.context.location.hash=url;}}});
  f.el('padType').focus=()=>{focusedVisible=f.activePage==='tools'&&!f.el('pad').hidden;};
  f.navigate('#home');f.run(between('function showNow(','$("nowSend").onclick'));
  buttons[0].onclick();
  assert.equal(focusedVisible,true);assert.equal(f.calls.filter(c=>c[0]==='padStart').length,1);
  buttons[1].onclick();assert.equal(f.context.location.hash,'#media');
});

function copyFixture(frameApp) {
  const calls=[],f=workspaceFixture();
  Object.assign(f.context,{window:{frameApp},api:async(path,body)=>{calls.push(JSON.parse(JSON.stringify([path,body])));return body.read?{text:'héllo 🎧\n',message:'Copied 8 characters from the headset\'s clipboard'}:{message:'Copied to this computer'};}});
  f.run(between('async function copyHeadsetClipboard()','$("clipFrom").onclick'));
  return {f,calls};
}
test('in the app, the headset’s clipboard is read and the app writes it, text untouched',async()=>{
  const written=[],{f,calls}=copyFixture({writeClipboard:async text=>{written.push(text);return true;}});
  const result=await f.run('copyHeadsetClipboard()');
  assert.deepEqual(calls,[['/api/clipboard',{read:true}]]);
  assert.deepEqual(written,['héllo 🎧\n']);
  assert.equal(result.message,'Copied 8 characters from the headset\'s clipboard');
  assert.equal(result.text,undefined,'the text is not handed on to be logged or toasted');
});
test('in a browser, the server sets the clipboard of the computer it runs on',async()=>{
  for(const frameApp of [undefined,{readClipboard(){}}]){
    const {f,calls}=copyFixture(frameApp);
    assert.equal((await f.run('copyHeadsetClipboard()')).message,'Copied to this computer');
    assert.deepEqual(calls,[['/api/clipboard',{toComputer:true}]]);
  }
});
test('a failed read writes nothing',async()=>{
  const written=[],f=workspaceFixture();
  Object.assign(f.context,{window:{frameApp:{writeClipboard:async t=>written.push(t)}},api:async()=>{throw new Error("The headset's clipboard is empty");}});
  f.run(between('async function copyHeadsetClipboard()','$("clipFrom").onclick'));
  await assert.rejects(f.run('copyHeadsetClipboard()'),/empty/);
  assert.deepEqual(written,[]);
});

test('the Control Center finds Type on the headset by typing, keyboard and clipboard words',()=>{
  const input=cc.catalog.find(item=>item.id==='input');
  assert.equal(input.title,'Type on the headset');
  assert.deepEqual(input.links[0],['#pad','Type on the headset']);
  for(const query of ['type','typing','keyboard','clipboard','copy paste','kde connect'])
    assert.ok(cc.matches(input,query,'all'),query);
  const files=cc.catalog.find(item=>item.id==='files');
  assert.ok(files.links.some(([href])=>href==='#pad'),'Send files points clipboard seekers to the right place');
});
