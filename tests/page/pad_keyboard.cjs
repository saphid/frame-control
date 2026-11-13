// Production keyboard handlers; only DOM/HTTP boundaries are replaced. Expected
// codes below come from Linux input-event-codes.h, not from the page's table.
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const test = require('node:test');
const html = readFileSync(require('node:path').join(__dirname, '../../ui/index.html'), 'utf8');
function between(start, end) {
  const a = html.indexOf(start), b = html.indexOf(end, a);
  assert.ok(a >= 0 && b > a, start);
  return html.slice(a, b);
}
function fixture() {
  const events = [], listeners = {}, elements = {};
  const on = (target, name, fn) => (listeners[target + ':' + name] ||= []).push(fn);
  const el = id => elements[id] ||= {classList:{remove(){}, toggle(){}}, addEventListener:(name, fn)=>on(id, name, fn)};
  const context = vm.createContext({pad:{state:'ready', captured:true, keys:new Set(), queue:[], sending:false},
    padSend:e=>events.push(JSON.parse(JSON.stringify(e))),
    padStart(){context.pad.state='starting';}, padShow(){}, $:el,
    window:{frameApp:{captureKeys(){}}, addEventListener:(name, fn)=>on('window', name, fn)},
    document:{hidden:false, pointerLockElement:null, addEventListener:(name, fn)=>on('document', name, fn),
      querySelector:el, exitPointerLock(){}},
    padType:el('padType')});
  vm.runInContext(between('const EVDEV = ', 'const CTRL_BUTTONS = '), context);
  vm.runInContext(between('const PAD_SPECIAL = ', 'const IS_MAC = '), context);
  vm.runInContext(between('const PAD_MODIFIERS = ', '// Touch: one finger'), context);
  vm.runInContext(between('// Capture phase, so the page', '// The text field: each keystroke'), context);
  vm.runInContext(between('document.addEventListener("pointerlockchange", () => {', '$("padArea").addEventListener("mousedown"'), context);
  vm.runInContext(between('padType.addEventListener("keydown", e => {', '// The caret stays after the space'), context);
  vm.runInContext(between('document.querySelector("#pad .pad-keys").addEventListener', 'clientPreferences.ready.then'), context);
  function fire(target, type, event={}) {
    const e = {ctrlKey:false, altKey:false, shiftKey:false, metaKey:false,
      preventDefault(){this.prevented=true;}, stopImmediatePropagation(){}, stopPropagation(){}, ...event};
    for (const fn of listeners[target + ':' + type] || []) fn(e);
    return e;
  }
  return {context, events, el, fire,
    key:(code, down, flags={})=>fire('window', down?'keydown':'keyup', {code, key:code, ...flags}),
    shortcut:name=>{el('padShortcut').value=name;el('padSendShortcut').onclick();}};
}
const tap = codes => [...codes.map(key=>[key,true]), ...[...codes].reverse().map(key=>[key,false])];
function vectors() {
  const out = [];
  function scenario(name, expected, action) {
    const f = fixture(); action(f);
    assert.equal(f.context.pad.keys.size, 0, name + ': no held browser keys');
    out.push({name, expected, events:f.events});
  }
  const keys = [['ControlLeft',29,'ctrlKey'],['ControlRight',97,'ctrlKey'],['AltLeft',56,'altKey'],
    ['AltRight',100,'altKey'],['ShiftLeft',42,'shiftKey'],['ShiftRight',54,'shiftKey'],
    ['MetaLeft',125,'metaKey'],['MetaRight',126,'metaKey'],['Tab',15],
    ['ArrowLeft',105],['ArrowUp',103],['ArrowRight',106],['ArrowDown',108],
    ...Array.from({length:12},(_,i)=>['F'+(i+1), i<10?59+i:87+i-10])];
  for (const [code, key, flag] of keys) scenario(code, tap([key]), f=>{
    f.key(code,true,flag?{[flag]:true}:{}); f.key(code,false);
  });
  const chords = [
    ['Ctrl+C', ['ControlLeft','KeyC'], [29,46], {ctrlKey:true}],
    ['Ctrl+V', ['ControlLeft','KeyV'], [29,47], {ctrlKey:true}],
    ['Ctrl+Z', ['ControlLeft','KeyZ'], [29,44], {ctrlKey:true}],
    ['Alt+Tab', ['AltLeft','Tab'], [56,15], {altKey:true}],
    ['Ctrl+Alt+T', ['ControlLeft','AltLeft','KeyT'], [29,56,20], {ctrlKey:true,altKey:true}],
    ['Shift+ArrowLeft', ['ShiftLeft','ArrowLeft'], [42,105], {shiftKey:true}],
    ['Super+T', ['MetaLeft','KeyT'], [125,20], {metaKey:true}],
  ];
  for (const [name,codes,expected,flags] of chords) scenario(name,tap(expected),f=>{
    // Deliver modifiers through their own keydowns; the chord key carries the complete snapshot.
    codes.forEach((code,i)=>f.key(code,true,i===codes.length-1?flags:
      code==='AltLeft'?{ctrlKey:codes.includes('ControlLeft'),altKey:true}:
      code==='ControlLeft'?{ctrlKey:true}:code==='ShiftLeft'?{shiftKey:true}:{metaKey:true}));
    [...codes].reverse().forEach((code,i)=>f.key(code,false,i===0?flags:
      code==='AltLeft'&&codes.includes('ControlLeft')?{ctrlKey:true}:{}));
  });
  for (const [name,codes] of Object.entries({copy:[29,46],paste:[29,47],undo:[29,44],switch:[56,15],terminal:[29,56,20],super:[125]})) {
    scenario('menu-'+name,tap(codes),f=>f.shortcut(name));
  }
  for (let i=1;i<=12;i++) scenario('menu-F'+i,tap([i<=10?58+i:76+i]),f=>f.shortcut('F'+i));
  scenario('Esc button',tap([1]),f=>f.fire('#pad .pad-keys','click',
    {target:{closest:()=>({dataset:{padKey:'14'}})}}));
  for (const cause of ['blur','pagehide','visibilitychange','pointerlockchange']) scenario('focus loss '+cause,tap([29,56,20]),f=>{
    f.key('ControlLeft',true,{ctrlKey:true}); f.key('AltLeft',true,{ctrlKey:true,altKey:true});
    f.key('KeyT',true,{ctrlKey:true,altKey:true});
    f.context.pad.state='error';
    if(cause==='visibilitychange') {f.context.document.hidden=true; f.fire('document',cause);}
    else if(cause==='pointerlockchange') f.fire('document',cause);
    else f.fire('window',cause);
    f.key('KeyT',false); // a late keyup cannot leave anything down or duplicate release
  });
  scenario('all modifiers released on blur',tap([29,56,42,125,20]),f=>{
    f.key('ControlLeft',true,{ctrlKey:true});
    f.key('AltLeft',true,{ctrlKey:true,altKey:true});
    f.key('ShiftLeft',true,{ctrlKey:true,altKey:true,shiftKey:true});
    f.key('MetaLeft',true,{ctrlKey:true,altKey:true,shiftKey:true,metaKey:true});
    f.key('KeyT',true,{ctrlKey:true,altKey:true,shiftKey:true,metaKey:true});
    f.fire('window','blur');
  });
  scenario('missed modifier keydown reconciled',tap([29,46]),f=>{
    f.key('KeyC',true,{ctrlKey:true});f.key('KeyC',false,{ctrlKey:true});f.key('ControlLeft',false);
  });
  scenario('Command swallows letter keyup',[[125,true],[46,true],[125,false],[46,false]],f=>{
    f.key('MetaLeft',true,{metaKey:true});f.key('KeyC',true,{metaKey:true});f.key('MetaLeft',false);
  });
  scenario('repeat does not duplicate holds',tap([29,46]),f=>{
    f.key('ControlLeft',true,{ctrlKey:true});f.key('ControlLeft',true,{ctrlKey:true,repeat:true});
    f.key('KeyC',true,{ctrlKey:true});f.key('KeyC',true,{ctrlKey:true,repeat:true});
    f.key('KeyC',false,{ctrlKey:true});f.key('ControlLeft',false);
  });
  for (const [key,code,mods,codes] of [['c','KeyC',{ctrlKey:true},[29,46]],['v','KeyV',{ctrlKey:true},[29,47]],
    ['z','KeyZ',{ctrlKey:true},[29,44]],['Tab','Tab',{altKey:true},[56,15]],
    ['t','KeyT',{ctrlKey:true,altKey:true},[29,56,20]],['C','KeyC',{ctrlKey:true,shiftKey:true},[29,42,46]],
    ['c','KeyC',{metaKey:true},[125,46]]]) {
    scenario('text field '+codes.join('+'),tap(codes),f=>{
      f.context.pad.captured=false;
      assert.equal(f.fire('padType','keydown',{key,code,...mods}).prevented,true);
    });
  }
  return out;
}
if (process.argv.includes('--vectors')) process.stdout.write(JSON.stringify(vectors()));
else {
  test('every key, chord, menu fallback and focus-loss case emits balanced input',()=>{
    for (const v of vectors()) {
      if (v.events.every(e=>'keyCode' in e)) assert.deepEqual(v.events.map(e=>[e.keyCode,e.down]),v.expected,v.name);
    }
  });
  test('Esc releases capture instead of claiming the browser can forward it',()=>{
    const f=fixture();f.key('ControlLeft',true,{ctrlKey:true});f.key('Escape',true);
    assert.equal(f.context.pad.captured,false);
    assert.deepEqual(f.events,[{keyCode:29,down:true},{keyCode:29,down:false}]);
  });
  test('pending Unicode/text input blocks raw capture/menu until drained',()=>{
    for (const pending of [{queued:1},{sending:true},{queue:[{key:'é'}]}]) {
      const f=fixture();Object.assign(f.context.pad,pending);f.shortcut('terminal');
      assert.deepEqual(f.events,[]);assert.match(f.el('padHint').textContent,/Wait for queued input/);
    }
  });
  test('text-field plain typing and IME remain beforeinput responsibilities',()=>{
    const f=fixture();f.context.pad.captured=false;
    assert.equal(f.fire('padType','keydown',{key:'a',code:'KeyA'}).prevented,undefined);
    f.fire('padType','keydown',{key:'x',code:'KeyX',ctrlKey:true,isComposing:true});
    assert.equal(f.fire('padType','keydown',{key:'@',code:'KeyQ',ctrlKey:true,altKey:true,
      getModifierState:name=>name==='AltGraph'}).prevented,undefined);
    assert.deepEqual(f.events,[]);
  });
  test('host-reserved shortcut note and controls live inside the typing tool',()=>{
    const section=between('id="pad"','</section>');
    for(const text of ['padShortcut','padSendShortcut','Esc stops mouse/keyboard capture','Alt+Tab','Command sends Linux Super']) assert.ok(section.includes(text),text);
  });
}
