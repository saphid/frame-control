/* Fixed local-download operations in Steam CEF. Plugin code never runs here. */
(async function(payload) {
  const api = window.SteamClient?.Downloads;
  let bridge = window.__frameyDownloadsBridgeV1;
  if (bridge && bridge.api !== api) {
    for (const key of [...bridge.sessions.keys()]) bridge.remove(key);
    bridge = null;
  }
  if (!bridge) {
    const sessions = new Map();
    const remove = key => {
      const item = sessions.get(key);
      if (item) item.closed = true;
      item?.handle?.unregister();
      sessions.delete(key);
      if (!sessions.size) {clearInterval(bridge.timer); bridge.timer = null;}
    };
    bridge = window.__frameyDownloadsBridgeV1 = {api, sessions, remove, timer:null, busy:false};
  }
  if (payload.action === 'close') {bridge.remove(payload.session); return null;}
  if (typeof api?.RegisterForDownloadItems !== 'function')
    throw Error('Steam download subscriptions are unavailable');
  let item = bridge.sessions.get(payload.session);
  const integer = (value, min, max=Number.MAX_SAFE_INTEGER) =>
    Number.isSafeInteger(value) && value >= min && value <= max;
  const project = rows => {
    if (!Array.isArray(rows) || rows.length > 2048) throw Error('Steam download list exceeds its limit');
    const ids = new Set();
    return rows.map(row => {
      if (!integer(row?.appid,1,4294967295) || ids.has(row.appid) ||
          !integer(row.queue_index,-1,10000) || typeof row.completed !== 'boolean' ||
          !integer(row.deferred_time ?? 0,0)) throw Error('Invalid local Steam download item');
      ids.add(row.appid);
      const infos = row.update_type_info ?? [];
      if (!Array.isArray(infos) || infos.length > 32) throw Error('Invalid Steam update sizes');
      return {appid:row.appid, queue_index:row.queue_index, completed:row.completed,
        deferred_time:row.deferred_time ?? 0, active:row.active === true, paused:row.paused === true,
        update_type_info:infos.map(info => {
          const progress = info.progress ?? [];
          if (!Array.isArray(progress) || progress.length > 32) throw Error('Invalid Steam update sizes');
          return {has_update:info.has_update === true, completed_update:info.completed_update === true,
            progress:progress.map(part => {
              if (!integer(part.bytes_total ?? 0,0)) throw Error('Invalid Steam download size');
              return {bytes_total:part.bytes_total ?? 0};
            })};
        })};
    });
  };
  if (!item) {
    if (payload.action !== 'read') throw Error('Reopen the download panel before queueing');
    if (bridge.sessions.size >= 4) throw Error('Too many Framey download sessions');
    item = {rows:[], ready:false, modern:false, version:0, changedVersion:null,
      touched:Date.now(), failure:null, handle:null};
    item.handle = api.RegisterForDownloadItems((...args) => {
      try {
        const rows = Array.isArray(args[1]) ? args[1] : args[0];
        if (!Array.isArray(rows)) throw Error('Invalid Steam download callback');
        const modern = rows.some(row => row && Object.hasOwn(row,'item_data'));
        if (modern) {
          item.modern = true;
          const local = rows.filter(row => row.remote_client_id === '0');
          if (local.length > 1) throw Error('Ambiguous local Steam download list');
          item.rows = project(local[0]?.item_data ?? []);
        } else {
          if (rows.length) item.modern = false;
          item.rows = project(rows);
        }
        item.ready = true; item.failure = null; item.version++;
      } catch (error) {item.ready = false; item.failure = error.message;}
    });
    if (typeof item.handle?.unregister !== 'function') throw Error('Steam download subscription failed');
    bridge.sessions.set(payload.session,item);
    if (!bridge.timer) bridge.timer = setInterval(() => {
      for (const [key,state] of bridge.sessions)
        if (Date.now() - state.touched > 15000) bridge.remove(key);
    },5000);
  }
  item.touched = Date.now();
  if (payload.action === 'read') {
    if (item.failure) throw Error(item.failure);
    return {ready:item.ready, items:item.rows, revision:item.version};
  }
  const ids = payload.appids;
  if (payload.action !== 'queue' || !Array.isArray(ids) || !ids.length || ids.length > 2048 ||
      ids.some(id => !integer(id,1,4294967295)) || new Set(ids).size !== ids.length)
    throw Error('Invalid download queue request');
  if (!item.ready || item.failure) throw Error('Steam download list is unavailable');
  if (bridge.busy) throw Error('Another download queue change is in progress');
  if (payload.revision !== item.version || item.changedVersion === item.version)
    throw Error('Downloads changed or are awaiting a Steam update; review the current list');
  for (const method of ['QueueAppUpdate','SetQueueIndex','ResumeAppUpdate'])
    if (typeof api[method] !== 'function') throw Error('Steam download queue controls are unavailable');
  const selected = ids.map(id => item.rows.find(row => row.appid === id));
  if (selected.some(row => !row || row.completed || row.queue_index !== -1))
    throw Error('Downloads changed; review the current list before queueing');
  const size = row => row.update_type_info.reduce((sum,info) => sum +
    (info.has_update && !info.completed_update ? info.progress.reduce((n,p) => n+p.bytes_total,0) : 0),0);
  selected.sort((a,b) => size(a)-size(b));
  const end = Math.max(-1,...item.rows.map(row => row.queue_index));
  const resume = item.rows.find(row => row.queue_index === 0)?.appid ?? selected[0].appid;
  const invoke = async (name,...args) => {
    if (item.closed || Date.now() > deadline) throw Error('Download queue operation expired or panel closed');
    let timer;
    let result;
    try {
      result = await Promise.race([api[name](...args,...(modern ? ['0'] : [])),
        new Promise((_,reject) => {timer = setTimeout(() => reject(Error('Steam queue operation timed out; refresh before retrying')),2000);})]);
    } finally {clearTimeout(timer);}
    if (result === false) throw Error(name+' was refused by Steam');
  };
  bridge.busy = true;
  item.changedVersion = item.version;
  const modern = item.modern, deadline = Date.now()+15000;
  let queued = 0;
  try {
    for (const [index,row] of selected.entries()) {
      const current = item.rows.find(current => current.appid === row.appid);
      if (!item.ready || !current || current.completed || current.queue_index !== -1)
        throw Error('Downloads changed during the queue operation');
      await invoke('QueueAppUpdate',row.appid);
      queued++;
      await invoke('SetQueueIndex',row.appid,end+1+index);
    }
    await invoke('ResumeAppUpdate',resume);
    return {queued};
  } catch (error) {
    throw Error('Queued '+queued+' of '+selected.length+' downloads; '+error.message);
  } finally {bridge.busy = false;}
})
