// The page's input queue, run in node against the real functions from ui/index.html.
import { readFileSync } from "fs";
const src = readFileSync(new URL("../../ui/index.html", import.meta.url), "utf8");
const grab = name => src.match(new RegExp(`(?:const ${name} = [^\\n]*\\n)|((?:async )?function ${name}\\([\\s\\S]*?\\n}\\n)`))[0];
const code = ["isMove", "padSend", "padKeep", "padFlush"].map(grab).join("");
const fail = msg => { console.log("FAIL " + msg); process.exit(1); };

function page(api) {
  const pad = { state: "ready", queue: [], sending: false };
  const shown = [];
  const fns = new Function("pad", "api", "padShow", "devGen", code + "; return { padSend, padFlush };")(pad, api, s => { shown.push(s); pad.state = s.state; }, 0);
  return { pad, shown, ...fns };
}

// While a request is in flight, events queue by these rules.
{
  const { pad, padSend } = page(() => new Promise(() => {}));  // a request that never returns
  const send = (state, e) => { pad.state = state; padSend(e); };
  send("ready", { singlehold: true });     // goes out, and stays in flight
  send("error", { dx: 3 });                // dropped: a stale move while broken
  send("error", { singlerelease: true });  // kept
  send("off", { singlerelease: true });    // off: nothing was held
  send("pairing", { key: "a" });           // kept while reconnecting
  send("pairing", { dx: 1 });              // dropped
  for (let i = 0; i < 250; i++) send("pairing", { key: "x" });
  send("pairing", { singlerelease: true }); // kept past the 200 cap
  const q = pad.queue;
  if (!(q[0].singlerelease && q[1].key === "a" && q.at(-1).singlerelease && !q.some(e => "dx" in e)
        && q.filter(e => e.singlerelease).length === 2)) fail("queueing " + JSON.stringify(q.slice(0, 3)) + " len " + q.length);
}

// A request that fails, or reaches a link that had dropped, keeps its keys and releases.
for (const [label, api] of [["request failed", async () => { throw new Error("offline"); }],
                            ["not sent", async () => ({ state: "starting", sent: false })],
                            ["queue full", async () => ({ state: "waiting", sent: false })]]) {
  const { pad, padSend, shown } = page(api);
  padSend({ dx: 5 });  // sent and lost: a move, fine to drop
  await new Promise(r => setTimeout(r, 0));
  pad.state = "ready";
  padSend({ singlerelease: true });
  padSend({ dx: 7 });  // queued while that request is in flight: stale once it fails
  padSend({ key: "b" });
  await new Promise(r => setTimeout(r, 0));
  const q = pad.queue;
  if (!(q.some(e => e.singlerelease) && q.some(e => e.key === "b") && !q.some(e => "dx" in e)))
    fail(label + ": " + JSON.stringify(q));
  if (!shown.length || shown.at(-1).state === "ready") fail(label + ": state not shown");
}
// Physical key releases survive focus loss during a failed/reconnecting request,
// including a full queue. A lost keyup must not strand Ctrl/Alt/Super on the Frame.
{
  const {pad,padSend}=page(()=>new Promise(()=>{}));
  padSend({keyCode:29,down:true});
  pad.state='pairing';
  for(let i=0;i<250;i++) padSend({key:'x'});
  pad.state='error';
  for(const code of [20,56,29,125]) padSend({keyCode:code,down:false});
  if(pad.queue.filter(e=>e.keyCode&&e.down===false).length!==4) fail('physical releases lost at queue cap');
}
for(const api of [async()=>{throw Error('offline');},async()=>({state:'starting',sent:false})]) {
  const {pad,padSend}=page(api);
  padSend({keyCode:29,down:false});
  await new Promise(r=>setTimeout(r,0));
  if(!pad.queue.some(e=>e.keyCode===29&&e.down===false)) fail('unacknowledged physical release was lost');
}

// Acknowledged text is removed locally, but its pending status must reach padShow
// so failures reported after acceptance are polled without another keypress.
{
  const { pad, padSend, shown } = page(async () => ({ state: "ready", sent: true, queued: 1 }));
  padSend({ key: "é" });
  await new Promise(r => setTimeout(r, 0));
  if (pad.queue.length || shown.at(-1)?.queued !== 1) fail("accepted text is not polled");
}

// Exercise the real status/poll function: queued text leaves pointer controls
// usable, still polls, shows an eventual error, and does not silently retry it.
{
  const pad = { state: "ready", queue: [] }, elements = {};
  let poll = null;
  const show = new Function("pad", "$", "PAD_STATES", "TOUCH", "padFlush", "devGen", "api",
    "setTimeout", "clearTimeout", grab("padShow") + "; return padShow;")(
    pad, id => elements[id] ||= { classList: { toggle() {} } }, {}, false, () => {}, 0,
    async () => ({ state: "error", message: "Text is retained; try again." }),
    fn => { poll = fn; return 1; }, () => { poll = null; });
  show({ state: "ready", queued: 1 });
  if (pad.state !== "ready" || !poll) fail("pending text disabled pointer or skipped poll");
  await poll();
  if (pad.state !== "error" || poll || !elements.padHint.textContent.includes("retained"))
    fail("asynchronous error not surfaced");
}
console.log("queue rules ok");
