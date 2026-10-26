/* Fixed, read-only projection executed in Steam CEF. No plugin source runs here. */
(function(payload) {
  const api = window.SteamClient?.GameSessions;
  let bridge = window.__frameyRunningBridgeV1;
  if (bridge && bridge.api !== api) {
    for (const key of [...bridge.sessions.keys()]) bridge.remove(key);
    bridge = null;
  }
  if (!bridge) {
    const sessions = new Map();
    const remove = key => {
      const item = sessions.get(key);
      item?.handle?.unregister();
      sessions.delete(key);
      if (!sessions.size) {clearInterval(bridge.timer); bridge.timer = null;}
    };
    bridge = window.__frameyRunningBridgeV1 = {api, sessions, remove, timer:null};
  }
  let item = bridge.sessions.get(payload.session);
  if (item && item.pluginId !== payload.pluginId) throw Error('Framey running session belongs to another plugin');
  if (!payload.active) {bridge.remove(payload.session); return null;}
  const store = window.SteamUIStore;
  if (!Array.isArray(store?.RunningApps)) throw Error('Steam running apps are unavailable');
  const apps = store.RunningApps;
  if (apps.length > 64) throw Error('Too many running Steam apps');
  const main = store.MainRunningApp;
  const project = app => [app.appid, app.display_name, app.sort_as, app.app_type, String(app.gameid),
    app.minutes_playtime_forever, app.minutes_playtime_last_two_weeks, app.rt_last_time_played];
  // Include a selected main app even if Steam's list changes between the reads.
  const rows = apps.map(project);
  if (main && !apps.some(app => app.appid === main.appid)) rows.push(project(main));
  const publicArt = value => {
    if (typeof value !== 'string' || value.length > 2048) return null;
    try {
      const url = new URL(value);
      if (url.protocol !== 'https:' || url.username || url.password || url.port ||
          !/(^|\.)steamstatic\.com$/.test(url.hostname) || !url.pathname.startsWith('/steam/apps/')) return null;
      return url.origin + url.pathname; // Never copy local artwork paths or query data.
    } catch (_) {return null;}
  };
  const artwork = [...apps, ...(main && !apps.some(app=>app.appid === main.appid) ? [main] : [])].map(app => {
    const art = window.appStore;
    const vertical = publicArt(art?.GetVerticalCapsuleURLForApp?.(app));
    const custom = art?.GetCustomVerticalCapsuleURLs?.(app);
    return [app.appid, vertical, Array.isArray(custom) ? custom.slice(0,8).map(publicArt).filter(Boolean) : []];
  });
  if (!item) {
    if (bridge.sessions.size >= 4) throw Error('Too many Framey running sessions');
    item = {pluginId:payload.pluginId, queue:[], sequence:0, touched:Date.now(), handle:null};
    if (typeof api?.RegisterForAppLifetimeNotifications === 'function') {
      item.handle = api.RegisterForAppLifetimeNotifications(event => {
        // This queue contains actual Steam notifications, never snapshot diffs.
        if (!Number.isSafeInteger(event?.unAppID) || event.unAppID <= 0 || typeof event.bRunning !== 'boolean') return;
        item.queue.push({sequence:++item.sequence, unAppID:event.unAppID, bRunning:event.bRunning});
        if (item.queue.length > 64) item.queue.shift();
      });
    }
    bridge.sessions.set(payload.session, item);
    if (!bridge.timer) bridge.timer = setInterval(() => {
      for (const [key, state] of bridge.sessions)
        if (Date.now() - state.touched > 15000) bridge.remove(key);
    }, 5000);
  }
  item.touched = Date.now();
  return {apps:rows, artwork, runningIds:apps.map(app => app.appid), mainAppId:main?.appid ?? null,
    events:item.queue.filter(event => event.sequence > payload.cursor), cursor:item.sequence,
    lifetimeAvailable:!!item.handle};
})
