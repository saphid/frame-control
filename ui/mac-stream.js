// Frame Control: one stream from the Mac's frame-mac-view agent, for the
// viewer pages (mac-view.html: one panel; mac-space.html: the Mac space).
// It connects over the agent's WebSocket, keeps a clock synced with the
// Mac's, decodes H.264 with WebCodecs (or JPEG), and acknowledges and
// reports on every frame: the agent paces itself on the acks
// (Controller.swift) and measures each frame's journey from the reports
// (Stats.swift). Input goes back the same way. Plain script, no modules:
// it defines window.MacStream.
"use strict";

// What this browser draws with, and how often it gives an animation frame
// when nothing else is going on (only for the numbers).
const MacEnv = (() => {
  const env = { gl: "", rafHz: 0, decoder: "" };
  try {
    const gl = document.createElement("canvas").getContext("webgl");
    const ext = gl && gl.getExtension("WEBGL_debug_renderer_info");
    env.gl = ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl ? "webgl" : "no webgl";
  } catch (e) { env.gl = "?"; }
  let n = 0, t0 = 0;
  const tick = t => {
    if (!t0) t0 = t;
    if (t - t0 < 1000) { n++; return requestAnimationFrame(tick); }
    env.rafHz = Math.round(n * 1000 / (t - t0));
  };
  requestAnimationFrame(tick);
  return env;
})();

async function macPickCodec(want) {
  if (want === "jpeg" || !("VideoDecoder" in window)) return "jpeg";
  try {
    const r = await VideoDecoder.isConfigSupported({ codec: "avc1.640028", optimizeForLatency: true });
    if (!r.supported) return "jpeg";
    // Whether this browser has a hardware H.264 decoder (for the numbers).
    const hw = await VideoDecoder.isConfigSupported({ codec: "avc1.640028", hardwareAcceleration: "prefer-hardware" })
      .catch(() => ({ supported: false }));
    MacEnv.decoder = hw.supported ? "h264 hardware" : "h264 software";
    return "h264";
  } catch (e) { return "jpeg"; }
}

function macStartCode(b, i) { return b[i] === 0 && b[i + 1] === 0 && (b[i + 2] === 1 || (b[i + 2] === 0 && b[i + 3] === 1)); }
function macSpsCodec(au) {
  for (let i = 0; i + 7 < au.length; i++) {
    if (!macStartCode(au, i)) continue;
    const n = au[i + 2] === 1 ? i + 3 : i + 4;
    if ((au[n] & 0x1f) === 7) return "avc1." + [au[n + 1], au[n + 2], au[n + 3]].map(b => b.toString(16).padStart(2, "0")).join("");
    i = n;
  }
  return "";
}

class MacStream {
  // opts: src; one of ticket (single use, from Frame Control) or space (a
  // Mac space key); codec, max, fps, bpp (optional); and callbacks:
  //   onFrame(image, width, height, seq, decodedAt): a VideoFrame or
  //     ImageBitmap, now the caller's to draw and close(). Call drawn() or
  //     presented() once it's on screen.
  //   onInfo(m), onStatus(text, sticky), onError(message), onClosed(reason),
  //   onStats(m), onBench(m)
  constructor(opts) {
    this.o = opts;
    this.src = opts.src || "test";
    this.stats = { frames: 0, keyFrames: 0, bytes: 0, dropped: 0, codec: "", errors: [], info: null };
    this.clock = { off: null, rtt: 0, samples: [], reported: 0 };
    this.reconnectKey = "";
    this.ws = null;
    this.dec = null;
    this.codec = "";
    this.codecString = "";
    this.needKey = true;
    this.closing = false;
    this.retry = 0;
    this.failedStarts = 0;
    this.lastError = "";
    this.lastKeyAsk = 0;
    this.reports = [];
    this.dropsToReport = 0;
    this.shownPending = null;
    this.rafQueued = false;
    this.inputId = 0;
    this.warmMs = 0;
    this.warmUntil = 0;
    this.warmTimer = 0;
    this.jpegBusy = false;
    this.pingTimer = 0;
    // Decoded, drawn and shown times go back in batches.
    this.reportTimer = setInterval(() => {
      if (!this.reports.length && !this.dropsToReport) return;
      this.send({ t: "fd", f: this.reports, drop: this.dropsToReport });
      this.reports = [];
      this.dropsToReport = 0;
    }, 250);
  }

  // ---- clock: the Mac measures each frame's journey on its own clock ----
  // NTP-style: the Mac's time minus ours, from the ping with the shortest
  // round trip lately (the least queueing, so the least error).
  toMac(ms) { return this.clock.off === null ? null : Math.round(ms * 1000 + this.clock.off); }
  onPong(m) {
    const now = performance.now(), rtt = now - m.c, clock = this.clock;
    clock.samples.push({ rtt, off: m.a - (m.c + now) / 2 * 1000 });
    if (clock.samples.length > 16) clock.samples.shift();
    const best = clock.samples.reduce((a, b) => (b.rtt < a.rtt ? b : a));
    clock.off = best.off;
    clock.rtt = best.rtt;
    if (now - clock.reported > 1000) {
      clock.reported = now;
      this.send({ t: "clock", rtt: +best.rtt.toFixed(2), dec: `${MacEnv.decoder}; ${MacEnv.gl}; raf ${MacEnv.rafHz} Hz` });
    }
  }
  startPings() {
    clearInterval(this.pingTimer);
    this.clock.samples = [];
    for (let i = 0; i < 10; i++) setTimeout(() => this.send({ t: "ping", c: performance.now() }), i * 40);
    this.pingTimer = setInterval(() => this.send({ t: "ping", c: performance.now() }), 1000);
  }

  // ---- reports ----
  dropped() { this.stats.dropped++; this.dropsToReport++; }
  // A frame drawn on a page: it's on screen from the next animation frame,
  // unless another replaces it first (then it was never seen).
  drawn(seq, decodedAt, drawnAt = performance.now()) {
    this.stats.frames++;
    if (this.shownPending) {
      const p = this.shownPending;
      this.reports.push([p.seq, this.toMac(p.dec), this.toMac(p.drawn), 0]);
    }
    this.shownPending = { seq, dec: decodedAt, drawn: drawnAt };
    if (this.rafQueued) return;
    this.rafQueued = true;
    requestAnimationFrame(() => {
      this.rafQueued = false;
      const p = this.shownPending, now = performance.now();
      this.shownPending = null;
      if (p && this.clock.off !== null) this.reports.push([p.seq, this.toMac(p.dec), this.toMac(p.drawn), this.toMac(now)]);
    });
  }
  // A decoded frame a newer one replaced before it was drawn.
  replaced(seq, decodedAt) {
    if (this.clock.off !== null) this.reports.push([seq, this.toMac(decodedAt), 0, 0]);
  }
  // A frame drawn into a WebXR frame: shown when that frame is.
  presented(seq, decodedAt, drawnAt, shownAt) {
    this.stats.frames++;
    if (this.clock.off !== null) this.reports.push([seq, this.toMac(decodedAt), this.toMac(drawnAt), this.toMac(shownAt)]);
  }

  // ---- connection ----
  send(obj) { if (this.ws && this.ws.readyState === 1) this.ws.send(JSON.stringify(obj)); }
  askKeyFrame() {
    const now = performance.now();
    if (now - this.lastKeyAsk < 500) return;
    this.lastKeyAsk = now;
    this.send({ t: "key-frame" });
  }
  status(text, sticky) { if (this.o.onStatus) this.o.onStatus(text, sticky); }

  async start() {
    this.codec = await macPickCodec(this.o.codec);
    this.stats.codec = this.codec;
    this.connect();
  }

  connect() {
    if (this.codec === "h264") this.makeDecoder();
    this.needKey = true;
    const o = this.o;
    const p = new URLSearchParams({ src: this.src, codec: this.codec, max: o.max || "1920", fps: o.fps || "60" });
    if (this.reconnectKey) p.set("r", this.reconnectKey);
    else if (o.space) p.set("s", o.space);
    else p.set("t", o.ticket || "");
    if (o.bpp) p.set("bpp", o.bpp);
    const ws = this.ws = new WebSocket(`ws://${location.host}/stream?${p}`);
    ws.binaryType = "arraybuffer";
    ws.onopen = () => { this.retry = 0; this.lastError = ""; this.startPings(); };
    ws.onmessage = ev => {
      if (typeof ev.data === "string") return this.control(JSON.parse(ev.data));
      const now = performance.now(), b = new Uint8Array(ev.data);
      this.stats.bytes += b.length;
      if (b.length < 18) return;
      // flags (1 = keyframe), pts µs, sequence number, input echoed; big-endian.
      const v = new DataView(ev.data), isKey = (b[0] & 1) === 1, seq = v.getUint32(9);
      this.send({ t: "rx", s: seq, r: this.toMac(now) });
      const payload = b.subarray(17);
      if (this.codec === "h264") this.onH264(isKey, seq, payload); else this.onJPEG(seq, payload);
    };
    ws.onclose = () => {
      if (this.ws === ws) this.ws = null;
      clearInterval(this.pingTimer);
      if (this.closing) return;
      // Refused before ever getting a key: the ticket expired or was revoked,
      // and retrying can't help.
      if (!this.reconnectKey && ++this.failedStarts >= 3) {
        this.status("This view has expired. Press Show in Frame Control on the Mac to open it again.", true);
        if (o.onClosed) o.onClosed("expired");
        return;
      }
      // The Mac may be asleep or the tunnel restarting: keep trying.
      this.retry = Math.min(this.retry + 1, 6);
      // Keep the Mac's reason (a missing permission, a closed window) on screen.
      this.status(this.lastError ? `${this.lastError} Retrying…` : "Lost the Mac. Reconnecting…", true);
      setTimeout(() => { if (!this.closing) this.connect(); }, 500 * 2 ** this.retry);
    };
  }

  control(m) {
    const o = this.o;
    if (m.t === "pong") return this.onPong(m);
    if (m.t === "stats") return o.onStats && o.onStats(m);
    if (m.t === "bench") return o.onBench && o.onBench(m);
    if (m.t === "hello") {
      this.reconnectKey = m.r;
      this.send({ t: "ack" });  // the ticket is spent only now
    } else if (m.t === "info") {
      this.stats.info = m;
      this.warmMs = Math.max(0, +m.warm || 0);
      if (o.onInfo) o.onInfo(m);
    } else if (m.t === "error") {
      this.stats.errors.push(m.message);
      this.lastError = m.message.replace(/\.?$/, ".");
      if (o.onError) o.onError(m.message);
    } else if (m.t === "close" || m.t === "closed") {
      this.stop();
      if (o.onClosed) o.onClosed(m.reason || "");
    }
  }

  stop() {
    this.closing = true;
    clearInterval(this.pingTimer);
    clearInterval(this.reportTimer);
    clearInterval(this.warmTimer);
    if (this.ws) try { this.ws.close(); } catch (e) {}
    if (this.dec) try { this.dec.close(); } catch (e) {}
  }

  // ---- H.264 ----
  makeDecoder() {
    if (this.dec) try { this.dec.close(); } catch (e) {}
    this.codecString = "";
    this.dec = new VideoDecoder({
      // The chunk's timestamp is the Mac's sequence number, to match reports up.
      output: frame => {
        if (this.closing) return frame.close();
        this.o.onFrame(frame, frame.displayWidth, frame.displayHeight, frame.timestamp, performance.now());
      },
      error: e => {
        this.stats.errors.push(String(e.message || e));
        this.needKey = true;
        if (this.closing) return;
        this.makeDecoder();
        this.askKeyFrame();
      },
    });
  }
  onH264(isKey, seq, au) {
    const dec = this.dec;
    if (isKey) {
      const cs = macSpsCodec(au);
      if (cs && (cs !== this.codecString || dec.state !== "configured")) {
        if (dec.state === "closed") this.makeDecoder();
        this.dec.configure({ codec: cs, optimizeForLatency: true, hardwareAcceleration: "no-preference" });
        this.codecString = this.stats.codec = cs;
      }
      this.stats.keyFrames++;
    }
    if (this.dec.state !== "configured" || (this.needKey && !isKey)) { this.dropped(); this.askKeyFrame(); return; }
    // Far behind: skip to the next keyframe rather than show old pictures late.
    // A few queued frames are fine: decoding catches up faster than a keyframe
    // crosses a slow link, and only the newest decoded frame gets drawn.
    if (!isKey && this.dec.decodeQueueSize > 10) { this.needKey = true; this.dropped(); this.askKeyFrame(); return; }
    this.needKey = false;
    this.dec.decode(new EncodedVideoChunk({ type: isKey ? "key" : "delta", timestamp: seq, data: au }));
  }

  // ---- JPEG ----
  onJPEG(seq, data) {
    if (this.jpegBusy) { this.dropped(); return; }
    this.jpegBusy = true;
    createImageBitmap(new Blob([data], { type: "image/jpeg" }))
      .then(bmp => { if (this.closing) bmp.close(); else this.o.onFrame(bmp, bmp.width, bmp.height, seq, performance.now()); })
      .catch(e => this.stats.errors.push(String(e)))
      .finally(() => { this.jpegBusy = false; });
  }

  // ---- input ----
  // x, y are 0..1 across the picture. Discrete input carries an id and when
  // it happened (the Mac's clock), so the Mac can tag the first frame that
  // could show its effect.
  stamp(m, at) {
    this.keepWarm();
    m.i = ++this.inputId;
    m.tv = this.toMac(at || performance.now());
    return m;
  }
  // Keep the Frame's Wi-Fi awake for a few seconds after input, when the agent asks.
  keepWarm() {
    if (!this.warmMs) return;
    this.warmUntil = performance.now() + 5000;
    if (this.warmTimer) return;
    this.warmTimer = setInterval(() => {
      if (performance.now() > this.warmUntil) { clearInterval(this.warmTimer); this.warmTimer = 0; return; }
      this.send({ t: "w" });
    }, this.warmMs);
  }
  move(x, y) { this.send({ t: "m", e: "move", x, y }); }
  down(x, y, button = 0, at) { this.send(this.stamp({ t: "m", e: "down", b: button, x, y }, at)); }
  up(x, y, button = 0) { this.send({ t: "m", e: "up", b: button, x, y }); }
  wheel(dx, dy, x, y, at) { this.send(this.stamp({ t: "wheel", dx, dy, x, y }, at)); }
  key(down, code, key, mods, at) {
    const m = { t: "k", e: down ? "down" : "up", code, key, mods };
    this.send(down ? this.stamp(m, at) : m);
  }
  text(s, at) { this.send(this.stamp({ t: "text", s }, at)); }
  release() { this.send({ t: "release" }); }
  focus() { this.send({ t: "focus" }); }
}
window.MacStream = MacStream;
window.MacEnv = MacEnv;
