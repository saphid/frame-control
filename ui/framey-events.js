/* Executed in Steam CEF, using Decky 3.3.0's loader/plugin_event envelope. */
(function(payload) {
  const backend = window.DeckyBackend;
  if (!backend?.addEventListener || !backend?.removeEventListener)
    throw Error('Decky backend events are unavailable');
  let bridge = window.__frameyEventBridgeV1;
  if (bridge && bridge.backend !== backend) {
    for (const key of [...bridge.sessions.keys()]) bridge.remove(key);
    bridge = null;
  }
  if (!bridge) {
    const sessions = new Map();
    const remove = key => {
      const item = sessions.get(key);
      if (item) backend.removeEventListener('loader/plugin_event', item.listener);
      sessions.delete(key);
      if (!sessions.size) {clearInterval(bridge.timer); bridge.timer = null;}
    };
    bridge = window.__frameyEventBridgeV1 = {backend, sessions, remove, timer:null};
  }
  const key = payload.session;
  let item = bridge.sessions.get(key);
  if (item && item.name !== payload.name) throw Error('Framey event session belongs to another plugin');
  if (!payload.events.length) {
    bridge.remove(key);
    return {events:[], cursor:0};
  }
  if (!item) {
    if (bridge.sessions.size >= 4) throw Error('Too many Framey event sessions');
    item = {name:payload.name, names:new Set(), queue:[], sequence:0, touched:Date.now()};
    item.listener = data => {
      if (data?.plugin !== item.name || !item.names.has(data.event) || !Array.isArray(data.args)) return;
      try {
        const encoded = JSON.stringify(data.args);
        if (encoded.length > 8192) return;
        item.queue.push({sequence:++item.sequence, event:data.event, args:JSON.parse(encoded)});
        // Bound both event count and the CDP response, even for a noisy plugin.
        while (item.queue.length > 64 || JSON.stringify(item.queue).length > 48*1024) item.queue.shift();
      } catch (_) {} // Non-JSON event data cannot cross the iframe bridge.
    };
    bridge.sessions.set(key, item);
    backend.addEventListener('loader/plugin_event', item.listener);
    if (!bridge.timer) bridge.timer = setInterval(() => {
      for (const [session, state] of bridge.sessions)
        if (Date.now() - state.touched > 15000) bridge.remove(session);
    }, 5000);
  }
  item.names = new Set(payload.events);
  item.touched = Date.now();
  return {events:item.queue.filter(event => event.sequence > payload.cursor && item.names.has(event.event)),
    cursor:item.sequence};
})
