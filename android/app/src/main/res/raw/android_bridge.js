(() => {
  const native = window.frameAppNative;
  if (!native || window.frameApp) return;
  let next = 1, installCb = null;
  const waiting = new Map();
  native.onmessage = e => {
    let m;
    try { m = JSON.parse(e.data); } catch { return; }
    if (m.installLink) { if (installCb) installCb(m.installLink); return; }
    const w = waiting.get(m.id);
    if (!w) return;
    waiting.delete(m.id);
    if (m.error) w.bad(new Error(m.error)); else w.ok(m.value);
  };
  const call = (name, arg) => new Promise((ok, bad) => {
    const id = next++;
    waiting.set(id, {ok, bad});
    native.postMessage(JSON.stringify({id, name, arg: arg ?? null}));
  });
  const CHUNK = 192 * 1024;
  const base64 = blob => new Promise((ok, bad) => {
    const r = new FileReader();
    r.onload = () => ok(String(r.result).split(',')[1]);
    r.onerror = () => bad(new Error("Couldn't read the file"));
    r.readAsDataURL(blob);
  });
  let saving = false;
  async function saveBlob(blob, name, image) {
    const max = image ? 64 * 1024 * 1024 : 2 * 1024 * 1024 * 1024;
    if (blob.size > max) throw new Error('File too large');
    const id = await call('startSave', {name, image, size: blob.size, mime: blob.type,
      head: image ? await base64(blob.slice(0, 32)) : ''});
    try {
      for (let offset = 0; offset < blob.size; offset += CHUNK) {
        await call('saveChunk', {token: id, offset, data: await base64(blob.slice(offset, offset + CHUNK))});
      }
      await call('finishSave', {token: id});
    } catch (e) {
      await call('abortSave', {token: id}).catch(() => {});
      throw e;
    }
  }
  async function saveItems(items, load) {
    if (saving) throw new Error('A save is already running');
    saving = true;
    let saved = 0;
    try {
      for (const item of items) {
        const {blob, name} = await load(item);
        await saveBlob(blob, name, true);
        saved++;
      }
      return {message: `Saved ${saved} image${saved === 1 ? '' : 's'} to Pictures/Frame Control`};
    } catch (e) {
      throw new Error(`Saved ${saved} of ${items.length} images. ${e.message}`);
    } finally { saving = false; }
  }
  window.frameApp = Object.freeze({
    platform: 'android',
    readClipboard: () => call('readClipboard'),
    setUpConnection: () => call('setUpConnection'),
    open: what => call('open', what),
    saveImages: images => saveItems(images, async image => {
      if (image.data.length > 90 * 1024 * 1024) throw new Error('Image too large');
      const binary = atob(image.data);
      return {name: image.name, blob: new Blob([Uint8Array.from(binary, c => c.charCodeAt(0))])};
    }),
    onInstallLink: cb => { installCb = cb; return call('installLinkReady'); },
  });
  // Adapt the pinned, unmodified desktop page after its scripts have loaded. Fetch,
  // encode and acknowledge one screenshot at a time, regardless of library size.
  document.addEventListener('DOMContentLoaded', () => {
    // The pinned page's explicit display:grid overrides the browser's [hidden]
    // rule, leaving the opaque name fallback over successfully loaded covers.
    if (document.head) {
      const style = document.createElement('style');
      style.textContent = '.capsule .fallback[hidden] { display: none; }';
      document.head.append(style);
    }
    window.saveToDevice = items => saveItems(items, async item => item);
    window.saveShots = (list, btn) => {
      if (!list.length) return;
      return act(`Save ${list.length} screenshot${list.length === 1 ? '' : 's'}`,
        () => saveItems(list, async s => ({blob: await shotBlob(s.id, false), name: s.file})), btn);
    };
    const originalApi = window.api;
    window.api = async (...args) => {
      try { return await originalApi(...args); }
      catch (e) {
        if (e.message.includes("local server isn't running")) {
          e.message = 'Lost the connection to the Frame. The app reconnects on its own.';
        }
        throw e;
      }
    };
  });
  // A WebView DownloadListener cannot read blob URLs. Handle download anchors
  // within this page and transfer bounded chunks to the native document picker.
  document.addEventListener('click', event => {
    const a = event.target.closest?.('a[download]');
    if (!a) return;
    const url = new URL(a.href, location.href);
    if (url.protocol === 'blob:' && url.origin === location.origin) {
      event.preventDefault();
      (async () => {
        if (saving) throw new Error('A save is already running');
        saving = true;
        try {
          const response = await fetch(url.href);
          await saveBlob(await response.blob(), a.download || 'Frame download', false);
        } finally { saving = false; }
      })().catch(e => alert(e.message));
    }
  }, true);
  window.frameAndroidDownloadBlob = async url => {
    const u = new URL(url);
    if (u.protocol !== 'blob:' || u.origin !== location.origin) return;
    if (saving) throw new Error('A save is already running');
    saving = true;
    try { await saveBlob(await (await fetch(url)).blob(), 'Frame download', false); }
    finally { saving = false; }
  };
})();
