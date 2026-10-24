"""Exercise the shipped desktop alert and its UI with a monotonic fake clock."""
import pathlib
import shutil
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'Node exercises production page JavaScript')
class DesktopBatteryComfort(unittest.TestCase):
    def test_alert_confirmation_and_lifecycle(self):
        page = (ROOT / 'ui/index.html').read_text(encoding='utf-8')
        code = page.split('// ---- Desktop-only low-battery comfort:')[1].split('// ---- battery ----')[0]
        code = code[code.index('class DesktopBatteryAlert'):]
        js = r'''
const assert = require('node:assert/strict');
const elements = new Map();
const $ = id => {
  if (!elements.has(id)) elements.set(id, {checked:false, textContent:''});
  return elements.get(id);
};
let now = 0, calls = [], toasts = [], devGen = 1, comfortActive = false;
const performance = {now:()=>now};
const listeners = {};
const document = {hidden:false, addEventListener:(name,fn)=>listeners[name]=fn};
const HOST = {mobile:false};
const window = {frameApp:{notify:(message,request)=>{calls.push({message,request});return Promise.resolve();}}};
const toast = message => toasts.push(message);
''' + code + r'''
(async () => {
  const low = {percent:15,status:'Discharging',watts:-4};
  const high = {...low,percent:20};
  const a = new DesktopBatteryAlert();
  assert.equal(a.sample(low,0),false);
  assert.equal(a.sample(low,1000),false); // rapid manual refreshes cannot confirm
  assert.equal(a.sample(low,30000),true);
  for (let t=60000;t<=900000;t+=30000) assert.equal(a.sample(low,t),false);
  assert.equal(a.sample(high,930000),false);
  assert.equal(a.sample(low,960000),false); // a recovery spike did not rearm
  assert.equal(a.sample(low,990000),false);
  a.sample(high,1020000); a.sample(high,1050000);
  assert.equal(a.sample(low,1080000),false);
  assert.equal(a.sample(low,1110000),true);
  const c = new DesktopBatteryAlert();
  c.sample(low,0); assert.equal(c.sample(low,30000),true);
  c.sample(high,60000); c.sample(high,90000);
  c.sample(low,120000); assert.equal(c.sample(low,150000),false); // ten minute cap
  assert.equal(c.sample(low,631000),false); // long gap requires fresh confirmation
  assert.equal(c.sample(low,661000),true);
  for (const bad of [null,{}, {...low,percent:null}, {...low,percent:NaN}, {...low,percent:-1},
      {...low,percent:101},{...low,percent:'10'}, {...low,status:'Unknown'},
      {...low,status:'Charging'}, {...low,status:'Full'}, {...low,status:'Not charging'},
      {...low,watts:0},{...low,watts:-0.5},{...low,watts:null},{...low,watts:NaN}]) {
    const b = new DesktopBatteryAlert();
    b.sample(low,0); assert.equal(b.sample(bad,30000),false);
    assert.equal(b.sample(low,60000),false); // unknown interrupts confirmation
  }
  const b = new DesktopBatteryAlert();
  b.sample(low,0); b.invalidate(); assert.equal(b.sample(low,30000),false);
  assert.equal(b.sample(low,121000),false); // stale gap
  assert.equal(b.sample(low,120000),false); // clock rollback
  desktopBatterySample(low); now=30000; desktopBatterySample(low);
  assert.equal(calls.length,0); // opt-in starts unchecked
  $('desktopBatteryAlert').checked=true; $('desktopBatteryAlert').onchange();
  now=60000;desktopBatterySample(low);now=90000;desktopBatterySample(low);
  assert.equal(calls.length,1); assert.equal(calls[0].request,false);
  assert.match(calls[0].message,/15%.*draining/);
  $('desktopBatteryAlert').checked=false;$('desktopBatteryAlert').onchange();
  $('desktopBatteryAlert').checked=true;$('desktopBatteryAlert').onchange();
  now=120000;desktopBatterySample(low);now=150000;desktopBatterySample(low);
  assert.equal(calls.length,1); // toggling does not clear episode latch
  desktopBattery.latched=false;desktopBattery.lastAlert=-Infinity;desktopBattery.invalidate();
  now=180000;desktopBatterySample(low);document.hidden=true;listeners.visibilitychange();
  document.hidden=false;now=210000;desktopBatterySample(low);assert.equal(calls.length,1);
  now=240000;desktopBatterySample(low);assert.equal(calls.length,2);
  desktopBattery.latched=false;desktopBattery.lastAlert=-Infinity;desktopBattery.invalidate();
  comfortActive=true;$('batteryAlert').checked=true;
  now=270000;desktopBatterySample(low);now=300000;desktopBatterySample(low);
  assert.equal(calls.length,2); // existing session owns battery alerts
  comfortActive=false;HOST.mobile=true;
  now=330000;desktopBatterySample(low);now=360000;desktopBatterySample(low);
  assert.equal(calls.length,2);
  HOST.mobile=false;
  window.frameApp.notify=()=>Promise.reject(Error('denied'));
  now=390000;desktopBatterySample(low);now=420000;desktopBatterySample(low);
  await new Promise(setImmediate);
  assert.match($('desktopBatteryStatus').textContent,/not confirmed/);
  now=450000;desktopBatterySample(low);
  assert.equal(toasts.length,3); // delivery failure does not retry on refresh
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
        result = subprocess.run(['node', '-e', js], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_existing_status_path_and_switch_reset(self):
        page = (ROOT / 'ui/index.html').read_text(encoding='utf-8')
        self.assertIn('desktopBatterySample(s.battery);', page)
        switch = page.split('if (link.device !== null && devId !== link.device)')[1].split('devGen++;')[0]
        self.assertIn('$("desktopBatteryAlert").checked = false;', switch)
        refresh = page.split('function refresh()')[1].split('async function refreshAfterAudio')[0]
        self.assertIn('desktopBattery.invalidate();', refresh)
        block = page.split('// ---- Desktop-only low-battery comfort:')[1].split('// ---- battery ----')[0]
        self.assertNotIn('setTimeout', block)
        self.assertNotIn('api(', block)
