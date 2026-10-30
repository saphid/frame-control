/* Framey panel compatibility layer. The iframe has an opaque origin and no UI key. */
(() => {
  'use strict';
  const R = window.SP_REACT = window.React;
  window.SP_REACTDOM = window.ReactDOM;
  const jsx = (type, props, key) => {
    const {children, ...elementProps} = props || {};
    if (key !== undefined) elementProps.key = key;
    return Object.prototype.hasOwnProperty.call(props || {}, 'children')
      ? R.createElement(type, elementProps, children)
      : R.createElement(type, elementProps);
  };
  window.SP_JSX = {jsx, jsxs:jsx, Fragment:R.Fragment};
  // Let plugins use optional chaining for Steam-only globals without inventing
  // user identity or suspend state in this isolated document.
  for (const name of ['App','appStore','appInfoStore','collectionStore']) window[name] = undefined;
  window.SuspendResumeStore = Object.freeze({});
  let runningApps = Object.freeze([]), mainRunningApp, runningAvailable = false;
  let runningArtwork = new Map();
  const runningListeners = new Set();
  let runningCursor = 0, runningRequest = null, runningTimer = null, runningClosed = false;
  window.SteamUIStore = Object.freeze({
    get RunningApps() {return runningApps;}, get MainRunningApp() {return mainRunningApp;},
    get FrameyRunningAvailable() {return runningAvailable;},
  });
  // Steam normally fills these token maps. Official plugins can safely use
  // their own fallback strings when the isolated panel has no Steam tokens.
  window.LocalizationManager = {m_rgLocalesToUse:[navigator.language || 'en'],
    m_mapTokens:new Map(), m_mapFallbackTokens:new Map([
      ['Settings_Bluetooth_Connected','Connected'],
      ['Settings_Bluetooth_NotConnected','Not connected'],
      ['Settings_Bluetooth_Devices','Devices'],
    ])};
  const root = document.getElementById('framey-root');
  const error = document.getElementById('framey-error');
  const toastRoot = document.getElementById('framey-toasts');
  let lastScrollTarget = null;
  function scrollTarget(element) {
    for (let node = element; node && node !== document; node = node.parentElement) {
      if (node.scrollHeight <= node.clientHeight + 1) continue;
      if (node === document.scrollingElement || /^(auto|scroll|overlay)$/.test(getComputedStyle(node).overflowY))
        return node;
    }
    return document.scrollingElement;
  }
  function scrollPlugin(direction) {
    if (direction !== 'up' && direction !== 'down') return false;
    const target = lastScrollTarget?.isConnected ? lastScrollTarget : document.scrollingElement;
    if (!target) return false;
    const before = target.scrollTop;
    const maximum = Math.max(0, target.scrollHeight - target.clientHeight);
    const step = Math.max(120, Math.round(target.clientHeight * 0.75));
    target.scrollTop = Math.max(0, Math.min(maximum, before + (direction === 'down' ? step : -step)));
    return target.scrollTop !== before;
  }
  const pending = new Map();
  const routes = new Map();
  const routeListeners = new Set();
  const routeHistory = [];
  let currentRoute = null;
  let currentParams = {};
  let nextId = 0;
  let plugin;
  const eventListeners = new Map();
  let eventCursor = 0, eventRevision = 0, subscribedRevision = -1;
  let eventRequest = null, eventTimer = null, eventClosed = false;
  // A sandboxed iframe has an opaque origin, so its native localStorage getter
  // throws SecurityError. Keep the familiar synchronous API inside the iframe;
  // the parent stores only this plugin's bounded snapshot under its own origin.
  const cache = new Map();
  const cacheLimit = 128 * 1024;
  const cacheSession = window.location?.hash.slice(1) || '';
  let acceptSeed, rejectSeed;
  const seeded = new Promise((resolve, reject) => {acceptSeed = resolve; rejectSeed = reject;});
  // Starting with an empty cache before the parent replies can overwrite a
  // plugin's saved settings. The parent answers even when its storage is
  // unavailable, in which case an empty seed is intentional.
  async function waitForSeed() {
    let timer;
    try {
      await Promise.race([seeded, new Promise((_, reject) => {
        timer = setTimeout(() => {
          acceptSeed = rejectSeed = null;
          reject(Error('Framey plugin storage did not initialize'));
        }, 5000);
      })]);
    } finally {clearTimeout(timer);}
  }
  const storage = {
    get length() {return cache.size;},
    key(index) {return [...cache.keys()][index] ?? null;},
    getItem(key) {return cache.get(String(key)) ?? null;},
    setItem(key, value) {
      const name = String(key), data = String(value);
      const next = new Map(cache); next.set(name, data);
      if (next.size > 64 || name.length > 256 || data.length > 65536 ||
          JSON.stringify(Object.fromEntries(next)).length > cacheLimit)
        throw new DOMException('Framey plugin cache is full', 'QuotaExceededError');
      cache.set(name, data); persistCache();
    },
    removeItem(key) {cache.delete(String(key)); persistCache();},
    clear() {cache.clear(); persistCache();},
  };
  function persistCache() {
    parent.postMessage({type:'framey:cache:save', session:cacheSession,
      entries:Object.fromEntries(cache)}, '*');
  }
  Object.defineProperty(window, 'localStorage', {configurable:true, value:storage});
  // localForage otherwise chooses the browser's exposed-but-denied IndexedDB
  // driver in an opaque iframe. Let it detect the bounded localStorage driver.
  Object.defineProperty(window, 'indexedDB', {configurable:true, value:undefined});
  parent.postMessage({type:'framey:cache:init', session:cacheSession}, '*');

  function request(method, args, legacy=false, type='framey:call', timeout=30000) {
    if (!/^[A-Za-z][A-Za-z0-9_]{0,63}$/.test(method)) return Promise.reject(Error('Invalid backend method'));
    const id = ++nextId;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { pending.delete(id); reject(Error('Decky backend timed out')); }, timeout);
      pending.set(id, {resolve, reject, timer});
      parent.postMessage({type, id, method, args, legacy, session:cacheSession}, '*');
    });
  }
  // The exact Wine Cellar archive expects Steam's loopback WebSocket origin.
  // This opaque iframe never gets that origin or a direct network connection.
  // Only its receipt-bound managed backend may reach the fixed local helper.
  const wineSockets = new Set();
  // The exact Syncthing frontend keeps its original loopback URLs. Its managed
  // backend uses a private socket belonging to the retained child, never a
  // general fetch proxy or an unverified listener on that TCP port.
  if (document.getElementById('framey-bundle')?.dataset?.syncthingHttp === '1') {
    // The dashboard starts several reads together, and its duplicate state
    // reads contend for the helper's ownership lock. Keep one fetch active.
    // Bound queue waiting separately: later reads still need the full RPC
    // budget after dispatch (at most 30 seconds waiting plus 30 executing).
    const fetchQueue = [];
    let fetchActive = false;
    function dispatchFetch() {
      if (fetchActive || !fetchQueue.length) return;
      const item = fetchQueue.shift();
      clearTimeout(item.timer);
      item.signal?.removeEventListener('abort', item.abort);
      const remaining = item.deadline - Date.now();
      if (remaining <= 0 || item.signal?.aborted) {
        item.reject(item.signal?.aborted ? new DOMException('Request aborted', 'AbortError')
          : Error('Decky backend timed out'));
        dispatchFetch();
        return;
      }
      fetchActive = true;
      request('framey_http_fetch', [item.args], true, 'framey:call', 30000)
        .then(item.resolve, item.reject).finally(() => {fetchActive = false; dispatchFetch();});
    }
    function queueFetch(args, signal) {
      if (fetchQueue.length >= 16) return Promise.reject(Error('Syncthing HTTP queue is full'));
      return new Promise((resolve, reject) => {
        const item = {args, signal, resolve, reject, deadline:Date.now()+30000};
        const remove = error => {
          const index = fetchQueue.indexOf(item);
          if (index < 0) return;
          fetchQueue.splice(index, 1);
          clearTimeout(item.timer);
          signal?.removeEventListener('abort', item.abort);
          reject(error);
        };
        item.abort = () => remove(new DOMException('Request aborted', 'AbortError'));
        item.timer = setTimeout(() => remove(Error('Decky backend timed out')), 30000);
        signal?.addEventListener('abort', item.abort, {once:true});
        fetchQueue.push(item);
        dispatchFetch();
      });
    }
    window.fetch = async (input, init={}) => {
      if (typeof input !== 'string' || !input.startsWith('http://127.0.0.1:58384/'))
        throw new TypeError('Syncthing HTTP origin is fixed');
      const url = new URL(input);
      if (url.origin !== 'http://127.0.0.1:58384' || url.username || url.password || url.hash)
        throw new TypeError('Syncthing HTTP origin is fixed');
      if (!init || typeof init !== 'object' || (init.body != null && init.body !== ''))
        throw new TypeError('Syncthing HTTP request body is unavailable');
      if (init.signal?.aborted) throw new DOMException('Request aborted', 'AbortError');
      const method = String(init.method || 'GET').toUpperCase();
      if (!['GET','POST'].includes(method)) throw new TypeError('Syncthing HTTP method is unavailable');
      const headers = Object.fromEntries(new Headers(init.headers || {}));
      if (Object.keys(headers).some(name => !['accept','content-type','authorization','x-api-key'].includes(name)))
        throw new TypeError('Syncthing HTTP header is unavailable');
      const reply = await queueFetch({method, path:url.pathname+url.search, headers}, init.signal);
      if (!reply?.success) throw Error(String(reply?.result || 'Syncthing HTTP bridge unavailable'));
      const data = reply.result;
      if (!data || !Number.isInteger(data.status) || data.status < 200 || data.status > 599 ||
          typeof data.body !== 'string' || data.body.length > 262144 ||
          typeof data.headers?.['content-type'] !== 'string')
        throw Error('Invalid Syncthing HTTP response');
      if (init.signal?.aborted) throw new DOMException('Request aborted', 'AbortError');
      return new Response([204,205,304].includes(data.status) ? null : data.body,
        {status:data.status, headers:{'content-type':data.headers['content-type']}});
    };
  }
  if (document.getElementById('framey-bundle')?.dataset?.wineSocket === '1') {
    class WineSocket extends EventTarget {
      constructor(url, protocols) {
        super();
        if (url !== 'ws://localhost:8887' || protocols !== undefined)
          throw new TypeError('Wine Cellar socket URL or protocol unavailable');
        this.url = url;
        this.readyState = WineSocket.CONNECTING;
        this.onopen = this.onmessage = this.onerror = this.onclose = null;
        this._token = null;
        this._sendChain = Promise.resolve();
        wineSockets.add(this);
        request('framey_ws_open', []).then(token => {
          if (typeof token !== 'string' || !/^[0-9a-f]{32}$/.test(token))
            throw Error('Invalid Wine Cellar socket token');
          this._token = token;
          if (this.readyState !== WineSocket.CONNECTING) {
            request('framey_ws_close', [token]).catch(() => {});
            return;
          }
          this.readyState = WineSocket.OPEN;
          this._emit('open', new Event('open'));
          this._poll();
        }).catch(error => this._fail(error));
      }
      _emit(kind, event) {
        this.dispatchEvent(event);
        try { this['on' + kind]?.(event); } catch (error) { console.warn('Wine Cellar event handler failed', error); }
      }
      _fail(error) {
        if (this.readyState === WineSocket.CLOSED) return;
        this._emit('error', new Event('error'));
        console.warn('Wine Cellar socket unavailable', error?.message || error);
        this.close();
      }
      async _poll() {
        if (this.readyState !== WineSocket.OPEN) return;
        try {
          const data = await request('framey_ws_poll', [this._token]);
          if (!data || !Array.isArray(data.messages) || data.messages.length > 32 || typeof data.closed !== 'boolean')
            throw Error('Invalid Wine Cellar socket response');
          for (const message of data.messages) {
            if (typeof message !== 'string' || message.length > 262144)
              throw Error('Invalid Wine Cellar socket message');
            if (this.readyState !== WineSocket.OPEN) break;
            this._emit('message', new MessageEvent('message', {data:message}));
          }
          if (data.closed) this.close();
          else if (this.readyState === WineSocket.OPEN) setTimeout(() => this._poll(), 50);
        } catch (error) { this._fail(error); }
      }
      send(data) {
        if (this.readyState !== WineSocket.OPEN)
          throw new DOMException('Wine Cellar socket is not open', 'InvalidStateError');
        if (typeof data !== 'string' || data.length > 65536)
          throw new TypeError('Wine Cellar socket accepts bounded text only');
        this._sendChain = this._sendChain.then(() => request('framey_ws_send', [this._token, data]));
        this._sendChain.catch(error => this._fail(error));
      }
      close() {
        if (this.readyState === WineSocket.CLOSED) return;
        this.readyState = WineSocket.CLOSED;
        wineSockets.delete(this);
        if (this._token) this._sendChain.catch(() => {}).then(() =>
          request('framey_ws_close', [this._token]).catch(() => {}));
        this._emit('close', new Event('close'));
      }
    }
    Object.assign(WineSocket, {CONNECTING:0, OPEN:1, CLOSING:2, CLOSED:3});
    Object.assign(WineSocket.prototype, {CONNECTING:0, OPEN:1, CLOSING:2, CLOSED:3});
    window.WebSocket = WineSocket;
  }
  function syncEvents() {
    if (eventClosed) return Promise.resolve();
    if (eventRequest) return eventRequest.then(() =>
      subscribedRevision !== eventRevision ? syncEvents() : undefined);
    const revision = eventRevision;
    eventRequest = request('events', [[...eventListeners.keys()], eventCursor], false, 'framey:events')
      .then(data => {
        subscribedRevision = revision;
        if (!data || !Array.isArray(data.events) || !Number.isSafeInteger(data.cursor))
          throw Error('Invalid Decky event response');
        eventCursor = data.cursor;
        for (const event of data.events) {
          if (!Array.isArray(event.args)) continue;
          for (const listener of eventListeners.get(event.event) || [])
            Promise.resolve().then(() => listener(...event.args)).catch(failure =>
              console.warn('Decky event listener failed', failure));
        }
      }).finally(() => {eventRequest = null;});
    return eventRequest.then(() => subscribedRevision !== eventRevision ? syncEvents() : undefined);
  }
  function refreshEvents() {
    clearTimeout(eventTimer);
    syncEvents().catch(failure => console.warn('Decky event bridge unavailable', failure.message))
      .finally(() => {
        clearTimeout(eventTimer);
        if (!eventClosed && eventListeners.size)
          eventTimer = setTimeout(refreshEvents, 1000);
      });
  }
  function addPluginEvent(event, listener) {
    if (typeof event !== 'string' || !/^[A-Za-z0-9_:/.-]{1,128}$/.test(event) || typeof listener !== 'function')
      throw Error('Invalid Decky event listener');
    if (!eventListeners.has(event)) {
      if (eventListeners.size >= 32) throw Error('Too many Decky event names');
      eventListeners.set(event, new Set());
    }
    eventListeners.get(event).add(listener);
    eventRevision++; refreshEvents();
    return listener; // Decky returns the registered callback, not a disposer.
  }
  function removePluginEvent(event, listener) {
    const listeners = eventListeners.get(event);
    if (!listeners?.delete(listener)) return;
    if (!listeners.size) eventListeners.delete(event);
    eventRevision++; refreshEvents();
  }
  async function ask(method, args, legacy=false) {
    // Subscribe before a backend call can emit its immediate response events.
    if (eventListeners.size && (eventRequest || subscribedRevision !== eventRevision)) await syncEvents();
    return request(method, args, legacy);
  }
  addEventListener('message', event => {
    if (event.source === parent && event.data?.type === 'framey:scroll' &&
        event.data.session === cacheSession) {
      if (event.data.direction !== 'up' && event.data.direction !== 'down') return;
      const moved = scrollPlugin(event.data.direction);
      parent.postMessage({type:'framey:scroll:result', session:cacheSession,
        direction:event.data.direction, moved}, '*');
      return;
    }
    if (event.source === parent && event.data?.type === 'framey:cache:seed' &&
        event.data.session === cacheSession && acceptSeed) {
      const entries = event.data.entries;
      const pairs = entries && typeof entries === 'object' && !Array.isArray(entries)
        ? Object.entries(entries) : null;
      if (!pairs || pairs.length > 64 ||
          pairs.some(([key, value]) => key.length > 256 || typeof value !== 'string' || value.length > 65536) ||
          JSON.stringify(entries).length > cacheLimit)
        rejectSeed(Error('Framey plugin storage returned invalid data'));
      else {
        for (const [key, value] of pairs) cache.set(key, value);
        acceptSeed();
      }
      acceptSeed = rejectSeed = null;
      return;
    }
    if (event.source !== parent || !event.data || event.data.type !== 'framey:reply') return;
    const item = pending.get(event.data.id);
    if (!item) return;
    pending.delete(event.data.id); clearTimeout(item.timer);
    if (event.data.error) item.reject(Error(event.data.error)); else item.resolve(event.data.result);
  });
  addEventListener('unload', () => {
    for (const socket of wineSockets) socket.close();
    eventClosed = true; clearTimeout(eventTimer);
    try { plugin?.onDismount?.(); } catch (_) {}
    // Parent tears down the remote session on close; CEF also expires it after 15s.
    parent.postMessage({type:'framey:events:close', session:cacheSession}, '*');
  });
  addEventListener('pointerup', event => {
    if (event.isTrusted) parent.postMessage({type:'framey:input', session:cacheSession}, '*');
  }, {passive:true});
  addEventListener('pointermove', event => {
    if (event.isTrusted) lastScrollTarget = scrollTarget(event.target);
  }, {passive:true});

  const passthrough = tag => ({children, ...props}) => R.createElement(tag, props, children);
  const Focusable = ({children, onActivate, onClick, onKeyDown, disabled, tabIndex, role, ...props}) => {
    const actionable=typeof onActivate==='function' || typeof onClick==='function';
    const activate = event => {
      if (disabled || event.defaultPrevented) return;
      event.stopPropagation();
      (onClick || onActivate)?.(event);
    };
    return R.createElement('div', {...props, role:role || (actionable ? 'button' : undefined),
      tabIndex:tabIndex ?? (actionable ? (disabled ? -1 : 0) : undefined),
      'aria-disabled':actionable && disabled ? true : undefined,
      onClick:actionable ? activate : undefined, onKeyDown:event=>{
        onKeyDown?.(event);
        if (actionable && !disabled && !event.defaultPrevented && event.target===event.currentTarget &&
            (event.key==='Enter' || event.key===' ')) {
          event.preventDefault();
          event.stopPropagation();
          (onActivate || onClick)?.(event);
        }
      }}, children);
  };
  const Field = ({label, description, children}) => R.createElement('label', null,
    R.createElement('strong', null, label), description && R.createElement('small', null, description), children);
  // DFL/@decky/ui Toggle uses value; ToggleField uses checked. Keep the
  // standalone control separate so persisted true settings render correctly.
  const Toggle = ({value, disabled, onChange}) => R.createElement('input', {
    type:'checkbox', checked:!!value, disabled:!!disabled,
    onChange:e=>{if(!disabled)onChange?.(e.target.checked);}});
  const ToggleField = ({label, description, checked, disabled, onChange}) => R.createElement(Field, {label, description},
    R.createElement('input', {type:'checkbox', checked:!!checked, disabled:!!disabled,
      onChange:e=>{if(!disabled)onChange?.(e.target.checked);}}));
  const DropdownItem = ({label, description, rgOptions=[], selectedOption, disabled, strDefaultLabel, onChange}) => {
    const choices=[];
    const option = entry => {
      const index=choices.push(entry)-1;
      return R.createElement('option', {key:index, value:String(index)}, entry.label);
    };
    const entries=(Array.isArray(rgOptions) ? rgOptions : []).map(entry =>
      Array.isArray(entry.options) ? R.createElement('optgroup', {key:String(entry.label), label:String(entry.label)},
        entry.options.map(option)) : option(entry));
    const selected=choices.findIndex(entry=>Object.is(entry.data, selectedOption));
    return R.createElement(Field, {label, description}, R.createElement('select', {
      value:selected < 0 ? '' : String(selected), disabled:!!disabled,
      onChange:e=>{const entry=choices[Number(e.target.value)];if(!disabled && entry)onChange?.(entry);}},
      selected < 0 && R.createElement('option', {value:'', disabled:true}, strDefaultLabel || 'Choose an option'),
      entries));
  };
  const ButtonItem = ({label, description, children, disabled, onClick}) => R.createElement(Field, {label, description},
    R.createElement('button', {type:'button', disabled:!!disabled,
      onClick:e=>{if(!disabled)onClick?.(e);}}, children || label));
  const DialogCheckbox = ({label, checked, defaultChecked, disabled, onChange}) =>
    R.createElement('label', null,
      R.createElement('input', {type:'checkbox', checked, defaultChecked, disabled:!!disabled,
        onChange:e=>{if(!disabled)onChange?.(e.target.checked);}}), label);
  const TextField = ({label, description, value, placeholder, disabled, bIsPassword,
    mustBeNumeric, mustBeURL, mustBeEmail, onChange}) => R.createElement(Field, {label, description},
    R.createElement('input', {type:bIsPassword?'password':mustBeNumeric?'number':mustBeURL?'url':mustBeEmail?'email':'text',
      value, placeholder, disabled:!!disabled, onChange:e=>{if(!disabled)onChange?.(e);}}));
  const SliderField = ({label, description, value, min=0, max=100, step=1, disabled, showValue, editableValue,
    valueSuffix='', onChange}) => R.createElement(Field, {label, description},
    R.createElement('input', {type:'range', value, min, max, step, disabled:!!disabled,
      'aria-label':typeof label==='string'?label:undefined,
      onChange:e=>{if(!disabled)onChange?.(Number(e.target.value));}}),
    editableValue ? R.createElement('span', null,
      R.createElement('input', {type:'number', value, min, max, step, disabled:!!disabled,
        'aria-label':typeof label==='string'?`${label} value`:'Slider value',
        style:{width:'7ch'}, onChange:e=>{
          const raw=e.target.value, next=Number(raw);
          if(!disabled && raw.trim()!=='' && e.target.validity?.valid!==false &&
              Number.isFinite(next) && next>=Number(min) && next<=Number(max)) onChange?.(next);
        }}), valueSuffix) : showValue && R.createElement('span', null, String(value) + valueSuffix));
  const PanelSection = ({title, children}) => R.createElement('section', null,
    title && R.createElement('h2', null, title), children);
  const Spinner = ({children}) => R.createElement('p', {role:'status'}, children || 'Loading…');
  const Tabs = ({tabs=[], activeTab, onShowTab}) => {
    const [selected, setSelected] = R.useState(tabs[0]?.id);
    const current = tabs.find(tab=>tab.id === (activeTab ?? selected)) || tabs[0];
    return R.createElement('div', null,
      R.createElement('div', {role:'tablist'}, ...tabs.map(tab=>R.createElement('button', {
        type:'button', key:tab.id, role:'tab', 'aria-selected':tab===current,
        disabled:!!tab.disabled, onClick:()=>{if(!tab.disabled){setSelected(tab.id);onShowTab?.(tab.id);}}}, tab.title))),
      R.createElement('div', {role:'tabpanel'}, current?.content));
  };
  const SidebarNavigation = ({pages=[], title}) => R.createElement('section', null,
    title && R.createElement('h2', null, title), R.createElement(Tabs, {
      tabs:pages.filter(page=>page.visible!==false).map((page,index)=>({
        id:page.route || String(index), title:page.title, content:page.content}))}));
  const ProgressBar = ({nProgress=0, value, max=100, indeterminate=false}) => R.createElement('progress', {
    value:indeterminate ? undefined : Math.max(0,Math.min(max,Number(value ?? nProgress)||0)), max});
  const ProgressBarWithInfo = ({sOperationText, ...props}) => R.createElement('div', null,
    ProgressBar(props), sOperationText == null ? null : R.createElement('small', {role:'status'}, sOperationText));
  const MenuItem = ({children, disabled, bDisabled, onClick, onSelected}) =>
    R.createElement('button', {type:'button',disabled:!!(disabled || bDisabled),
      onClick:event=>{if(!disabled && !bDisabled)(onClick || onSelected)?.(event);}}, children);
  const ConfirmModal = ({strTitle, strDescription, strOKButtonText, strCancelButtonText,
    strMiddleButtonText, onOK, onCancel, onMiddleButton, closeModal, frameySetModalBusy,
    bOKDisabled, bCancelDisabled, bMiddleDisabled, bAlertDialog, children}) => {
    const inFlight = R.useRef(false);
    const [busy, setBusy] = R.useState(false);
    const [error, setError] = R.useState('');
    const action = (callback, disabled) => () => {
      if (disabled || inFlight.current) return;
      let result;
      try {result = callback?.();}
      catch (failure) {setError(String(failure?.message || failure)); return;}
      if (result && typeof result.then === 'function') {
        inFlight.current = true;
        setBusy(true);
        frameySetModalBusy?.(true);
        setError('');
        return Promise.resolve(result).then(() => {
          inFlight.current = false;
          frameySetModalBusy?.(false);
          closeModal?.();
        }, failure => {
          inFlight.current = false;
          setBusy(false);
          frameySetModalBusy?.(false);
          setError(String(failure?.message || failure));
        });
      }
      closeModal?.();
    };
    return R.createElement('section', null,
      R.createElement('h2', null, strTitle),
      strDescription && R.createElement('div', null, strDescription), children,
      error && R.createElement('p', {role:'alert'}, error),
      R.createElement('button', {type:'button', disabled:!!bOKDisabled || busy,
        onClick:action(onOK, bOKDisabled)}, strOKButtonText || 'OK'),
      onMiddleButton && R.createElement('button', {type:'button', disabled:!!bMiddleDisabled || busy,
        onClick:action(onMiddleButton, bMiddleDisabled)}, strMiddleButtonText || 'More'),
      !bAlertDialog && R.createElement('button', {type:'button', disabled:!!bCancelDisabled || busy,
        onClick:action(onCancel, bCancelDisabled)}, strCancelButtonText || 'Cancel'));
  };
  const modalRoot = window.ReactDOM.createRoot(document.getElementById('framey-modal'));
  const modals = [];
  let modalId = 0;
  const renderModals = () => {
    document.getElementById('framey-root').inert = modals.length > 0;
    modalRoot.render(modals.length ? modals.map((modal,index) =>
    R.createElement('section', {key:modal.id, className:'framey-dialog', tabIndex:-1,
      ref:node=>{modal.node=node;}, hidden:index!==modals.length-1,
      role:'dialog', 'aria-modal':index===modals.length-1 ? true : undefined,
      'aria-label':typeof modal.element?.props?.strTitle==='string' ? modal.element.props.strTitle : 'Plugin dialog'},
      !modal.element?.props?.bHideCloseIcon && R.createElement('button', {
        type:'button', disabled:!!modal.running || !!modal.element?.props?.bCancelDisabled,
        onClick:()=>dismissModal(modal)}, 'Close'), modal.element)) : null);
  };
  function dismissModal(modal) {
    if (modal.running || modal.element?.props?.bCancelDisabled) return;
    modal.element?.props?.onCancel?.();
    modal.dismiss();
  }
  addEventListener('keydown', event => {
    const modal=modals.at(-1);
    if (!modal) return;
    if (event.key === 'Tab') {
      const controls = [...(modal.node?.querySelectorAll('button,input,select,textarea,a[href],[tabindex]') || [])]
        .filter(node=>!node.disabled && node.tabIndex>=0 && node.getClientRects().length);
      const index=controls.indexOf(document.activeElement);
      if (index < 0 || (!event.shiftKey && index===controls.length-1) || (event.shiftKey && index===0)) {
        event.preventDefault();
        (event.shiftKey ? controls.at(-1) : controls[0])?.focus();
      }
      return;
    }
    if (event.key !== 'Escape') return;
    event.preventDefault();
    if (modal.running) return;
    if (modal.element?.props?.onEscKeypress) modal.element.props.onEscKeypress();
    else dismissModal(modal);
  });
  const localPath = path => typeof path === 'string' && path.length <= 120 &&
    /^\/[A-Za-z0-9/_-]+$/.test(path) && !path.includes('//');
  const routePattern = path => typeof path === 'string' && path.length <= 120 &&
    /^\/(?:[A-Za-z0-9_-]+|:[A-Za-z][A-Za-z0-9_]*\??)(?:\/(?:[A-Za-z0-9_-]+|:[A-Za-z][A-Za-z0-9_]*\??))*$/.test(path) &&
    !/\?\//.test(path) &&
    new Set([...path.matchAll(/:([A-Za-z][A-Za-z0-9_]*)\??/g)].map(match => match[1])).size ===
      [...path.matchAll(/:([A-Za-z][A-Za-z0-9_]*)\??/g)].length;
  function matchRoute(pattern, path) {
    const expected = pattern.slice(1).split('/');
    const actual = path.slice(1).split('/');
    if (actual.length > expected.length) return null;
    const params = {};
    for (let index = 0; index < expected.length; index++) {
      const segment = expected[index], value = actual[index];
      if (segment[0] === ':') {
        const optional = segment.endsWith('?'), name = segment.slice(1, optional ? -1 : undefined);
        if (value === undefined) { if (!optional) return null; }
        else params[name] = value;
      } else if (segment !== value) return null;
    }
    return params;
  }
  function activeRoute(path) {
    if (routes.has(path)) return {component:routes.get(path), params:{}};
    for (const [pattern, component] of routes) {
      const params = matchRoute(pattern, path);
      if (params) return {component, params};
    }
    return null;
  }
  function showRoute(path, match) {
    currentRoute = path;
    currentParams = match?.params || {};
    for (const listener of routeListeners) listener(path);
    return true;
  }
  function navigate(path) {
    if (path !== null && !localPath(path)) return false;
    const match = path === null ? null : activeRoute(path);
    if (path !== null && !match) return false;
    if (path === null) routeHistory.length = 0;
    else if (path !== currentRoute) {
      routeHistory.push(currentRoute);
      if (routeHistory.length > 32) routeHistory.shift();
    }
    return showRoute(path, match);
  }
  function navigateBack() {
    while (routeHistory.length) {
      const previous = routeHistory.pop();
      const match = previous === null ? null : activeRoute(previous);
      if (previous === null || match) return showRoute(previous, match);
    }
    return navigate(null);
  }
  const routerHook = {
    addRoute(path, component) {
      if (!routePattern(path) ||
          (typeof component !== 'function' && !R.isValidElement(component)))
        throw Error('Framey route needs a local path and React component');
      routes.set(path, component);
      return () => routerHook.removeRoute(path);
    },
    removeRoute(path) {routes.delete(path); if(currentRoute && !activeRoute(currentRoute)) navigate(null);},
    // Steam routes and global components have no equivalent in the isolated panel.
    addPatch:()=>()=>{}, removePatch:()=>{}, addGlobalComponent:()=>{}, removeGlobalComponent:()=>{},
  };
  const noPatch = () => {const undo=()=>{};undo.unpatch=undo;return undo;};
  class MissingSteamComponent {}
  const showModal = element => {
    let resolveClosed;
    const ClosedPromise = new Promise(resolve=>{resolveClosed=resolve;});
    const modal = {id:++modalId, previousFocus:document.activeElement, source:element};
    const Close = () => {
      const index=modals.indexOf(modal);
      if (index < 0) return;
      const wasTop=index===modals.length-1;
      modals.splice(index,1);
      renderModals();
      resolveClosed();
      if (wasTop) setTimeout(()=>{
        if (modals.length) modals.at(-1).node?.focus();
        else if (modal.previousFocus?.isConnected) modal.previousFocus.focus();
      },0);
    };
    modal.dismiss = () => {
      if (!modals.includes(modal)) return;
      const callback=modal.source?.props?.closeModal;
      if (callback !== modal.dismiss) callback?.();
      Close();
    };
    const setModalBusy = busy => {
      if (!modals.includes(modal)) return;
      modal.running=!!busy;
      renderModals();
    };
    const decorate = next => R.isValidElement(next) ?
      R.cloneElement(next, {closeModal:modal.dismiss, frameySetModalBusy:setModalBusy}) : next;
    modal.element = decorate(element);
    modals.push(modal);
    renderModals();
    setTimeout(()=>{if(modals.at(-1)===modal) modal.node?.focus();},0);
    return {Close, ClosedPromise, Update:next=>{
      if (!modals.includes(modal)) return;
      // Keep replacement dialogs dismissible inside this isolated host too.
      modal.source=next;
      modal.element=decorate(next);
      renderModals();
    }};
  };
  // These are Framey's own styles and components, never Steam's webpack cache.
  // Keep the registry finite: an unknown Steam implementation stays unavailable.
  const classModules = new Map(Object.entries({
    'framey/spinner': {SpinnerLoaderContainer:'framey-spinner', ContainerBackground:'framey-loading',
      LoadingStatus:'framey-status', Medium:'framey-medium'},
    'framey/footer': {QuickAccessFooter:'framey-footer', BasicFooter:'framey-footer'},
    'framey/app-details': {AppDetailSectionList:'framey-sections', AppActionButton:'framey-action'},
    'framey/play-button': {PlayButtonContainer:'framey-actions', ButtonChild:'framey-button-child',
      Green:'framey-green', PlayButton:'framey-action'},
    'framey/library-image': {LongTitles:'framey-long-title', GreyBackground:'framey-muted', Image:'framey-image'},
    'framey/library': {GamepadLibrary:'framey-library'},
    'framey/focus': {FocusRingRoot:'framey-focus', FocusRing:'framey-focus'},
  }).map(([id, classes]) => [id, Object.freeze(classes)]));
  const localModules = new Map(classModules);
  const moduleVariants = module => [module?.default, module].filter(value => value != null);
  function findModule(filter) {
    for (const module of localModules.values())
      for (const value of moduleVariants(module)) if (filter(value)) return value;
  }
  function findModuleDetailsByExport(filter, minExports) {
    for (const [id, module] of localModules)
      for (const value of moduleVariants(module)) {
        if (typeof value !== 'object' || (minExports && Object.keys(value).length < minExports)) continue;
        for (const name in value) {
          if (!value[name]) continue;
          // DFL tolerates filters that dereference an incompatible export.
          try { if (filter(value[name], name)) return [value, value[name], name, id]; } catch (_) {}
        }
      }
    return [undefined, undefined, undefined, undefined];
  }
  function findModuleChild(filter) {
    for (const module of localModules.values())
      for (const value of moduleVariants(module)) {
        const result = filter(value);
        if (result) return result;
      }
  }
  function createModuleMapping(filter) {
    const mapping = new Map();
    for (const [id, module] of localModules)
      for (const value of moduleVariants(module)) if (filter(value)) mapping.set(id, value);
    return mapping;
  }
  const DFL = window.DFL = {
    definePlugin: init => init,
    PanelSection, PanelSectionRow: passthrough('div'), Field, ToggleField, DropdownItem,
    Dropdown: DropdownItem, ButtonItem, DialogCheckbox, TextField, SliderField,
    Focusable, ScrollPanel: passthrough('div'), ScrollPanelGroup: passthrough('div'),
    DialogButton: passthrough('button'), DialogButtonPrimary: passthrough('button'), ConfirmModal,
    DialogButtonSecondary: passthrough('button'), Button: ButtonItem, GamepadButton: passthrough('button'),
    Toggle, Spinner, SteamSpinner:Spinner, Tabs, SidebarNavigation,
    SuspensefulImage:({alt='', ...props})=>R.createElement('img', {...props, alt}),
    Marquee:passthrough('span'), DialogBody:passthrough('div'), DialogBodyText:passthrough('p'),
    DialogHeader:passthrough('h2'), DialogSubHeader:passthrough('h3'), DialogFooter:passthrough('footer'),
    DialogLabel:passthrough('label'), DialogControlsSection:passthrough('section'),
    DialogControlsSectionHeader:passthrough('h3'), ModalRoot:passthrough('section'),
    ModalPosition:passthrough('div'),
    Menu:passthrough('div'), MenuGroup:passthrough('section'), MenuItem,
    ProgressBar, ProgressBarItem:ProgressBar, ProgressBarWithInfo,
    gamepadDialogClasses:{}, quickAccessMenuClasses:{}, gamepadTabbedPageClasses:{},
    gamepadSliderClasses:{}, gamepadContextMenuClasses:{}, scrollPanelClasses:{},
    quickAccessControlsClasses:{}, mainMenuAppRunningClasses:{}, libraryAssetImageClasses:{},
    joinClassNames:(...names)=>names.filter(Boolean).join(' '),
    sleep:ms=>new Promise(resolve=>setTimeout(resolve,Math.max(0,Number(ms)||0))),
    staticClasses: {Title:'framey-title'},
    Navigation: {Navigate:navigate, NavigateBack:navigateBack, CloseSideMenus:()=>navigate(null),
      NavigateToExternalWeb: url => { if (/^https:\/\//.test(url)) window.open(url, '_blank', 'noopener'); }},
    showModal, showContextMenu:showModal,
    // Steam app, library, and store patches have no target inside this panel.
    afterPatch:noPatch, beforePatch:noPatch, replacePatch:noPatch, createReactTreePatcher:noPatch,
    // The isolated panel has no Steam React root. Legacy plugins can inspect
    // this null result and keep their own controls without patching Steam UI.
    getReactRoot: () => null, findInReactTree: () => null,
    findModule, findModuleChild, findModuleDetailsByExport,
    findModuleByExport:(filter, minExports)=>findModuleDetailsByExport(filter,minExports)[0],
    findModuleExport:(filter, minExports)=>findModuleDetailsByExport(filter,minExports)[1],
    createModuleMapping, findAllModules:filter=>[...createModuleMapping(filter).values()],
    findClassModule:filter=>[...classModules.values()].find(filter),
    findClass:(id,name)=>classModules.get(id)?.[name],
    findClassByName:name=>[...classModules.values()].find(classes=>classes[name])?.[name],
    unminifyClass:token=>{
      for(const classes of classModules.values())
        for(const name of Object.keys(classes)) if(classes[name]===token)return name;
    },
    findSP:()=>null,
    // Some legacy panels dereference the type of a Steam-only component before
    // installing a patch. Give them an inert local type; no Steam tree is
    // rendered or patched in this isolated iframe.
    fakeRenderComponent:()=>({type:MissingSteamComponent}),
    appDetailsClasses: {}, appDetailsHeaderClasses: {},
    useParams: () => currentParams,
  };
  localModules.set('framey/components', Object.freeze(Object.fromEntries(
    Object.entries(DFL).filter(([name,value])=>typeof value==='function' && /^[A-Z]/.test(name)))));
  // Some panels eagerly look up the optional Steam UI sound player. Allow the
  // lookup, but never claim playback or expose Steam's mutable audio store.
  localModules.set('framey/ui-audio', Object.freeze({UIAudio:Object.freeze({
    GamepadUIAudio:Object.freeze({available:false, AudioPlaybackManager:Object.freeze({
      PlayAudioURL:()=>{throw Error('Steam UI sound playback is not supported in Framey');},
    })}),
  })}));
  // Unsupported subscriptions remain inert. Lifetime callbacks below relay
  // actual Steam notifications; no power, input or launch events are invented.
  const subscription = () => {const dispose=()=>{};dispose.unregister=dispose;return dispose;};
  const register = names => Object.fromEntries(names.map(name=>[name,subscription]));
  const steamLanguage = () => {
    const locale = (navigator.language || 'en').toLowerCase();
    if (/^zh-(tw|hk|mo|hant)/.test(locale)) return 'tchinese';
    if (locale.startsWith('pt-br')) return 'brazilian';
    if (locale.startsWith('es-419')) return 'latam';
    return ({en:'english',de:'german',fr:'french',es:'spanish',it:'italian',ja:'japanese',
      ko:'koreana',zh:'schinese',ru:'russian',pl:'polish',pt:'portuguese',nl:'dutch',
      da:'danish',fi:'finnish',sv:'swedish',no:'norwegian',cs:'czech',hu:'hungarian',
      ro:'romanian',th:'thai',tr:'turkish',vi:'vietnamese',uk:'ukrainian',id:'indonesian'
    })[locale.split('-')[0]] || 'english';
  };
  window.SteamClient = {
    Settings:{GetCurrentLanguage:async()=>steamLanguage(),
      GetGlobalCompatTools:()=>request('GetGlobalCompatTools',[],false,'framey:steam'),
      ...register(['RegisterForSettingsChanges'])},
    Apps:register(['RegisterForAppDetails','RegisterForGameActionTaskChange',
      'RegisterForGameActionStart','RegisterForGameActionEnd','RegisterForGameActionUserRequest']),
    GameSessions:{...register(['RegisterForScreenshotNotification']),
      RegisterForAppLifetimeNotifications:listener=>{
        if (typeof listener !== 'function') throw Error('Invalid Steam lifetime listener');
        if (runningListeners.size >= 32) throw Error('Too many Steam lifetime listeners');
        runningListeners.add(listener);
        const dispose=()=>runningListeners.delete(listener);
        dispose.unregister=dispose; return dispose;
      }},
    System:{...register(['RegisterForOnResumeFromSuspend','RegisterForOnSuspendRequest']),
      GetSystemInfo:()=>request('GetSystemInfo',[],false,'framey:steam'),
      UI:register(['RegisterForFocusChangeEvents','RegisterForSystemKeyEvents'])},
    Input:register(['RegisterForControllerInputMessages','RegisterForControllerStateChanges']),
    User:{...register(['RegisterForLoginStateChange','RegisterForPrepareForSystemSuspendProgress',
      'RegisterForResumeSuspendedGamesProgress','RegisterForCurrentUserChanges']),
      GetIPCountry:()=>request('GetIPCountry',[],false,'framey:steam')},
    InstallFolder:{GetInstallFolders:()=>request('GetInstallFolders',[],false,'framey:steam')},
    Overlay:register(['RegisterForOverlayActivated']),
    UI:register(['RegisterForUIModeChanged']),
    // This is private plugin cache, not Steam's account/global JSON store.
    Storage:{
      GetJSON:async key=>{
        const value=storage.getItem('steam-client:'+String(key));
        if(value===null)throw Error('Not found');
        return value;
      },
      SetObject:async(key,value)=>{
        const encoded=JSON.stringify(value);
        if(encoded===undefined)throw Error('SteamClient.Storage requires a JSON value');
        storage.setItem('steam-client:'+String(key),encoded);
      },
    },
  };
  DFL.Router = {...DFL.Navigation,
    get RunningApps() {return runningApps;}, get MainRunningApp() {return mainRunningApp;},
  };
  if (document.getElementById('framey-bundle')?.dataset?.downloads === '1') {
    const listeners = new Set();
    let timer = null, polling = null, closed = false, available = false, revision = 0;
    const close = () => {
      clearTimeout(timer); available = false;
      parent.postMessage({type:'framey:downloads:close',session:cacheSession},'*');
    };
    const poll = () => {
      if (closed || !listeners.size || polling) return;
      polling = request('read',[],false,'framey:downloads').then(data => {
        if (!data?.ready || !Array.isArray(data.items) || data.items.length > 2048 ||
            !Number.isSafeInteger(data.revision) || data.revision < 1)
          throw Error('Steam has not supplied its download list yet');
        if (closed || !listeners.size) return;
        available = true;
        revision = data.revision;
        if (error.textContent.startsWith('Download queue unavailable:')) error.textContent = '';
        for (const listener of listeners) listener(true,[{remote_client_id:'0',item_data:data.items}]);
      }).catch(failure => {
        available = false;
        if (!closed && listeners.size) error.textContent = 'Download queue unavailable: '+failure.message;
      }).finally(() => {
        polling = null;
        if (!closed && listeners.size) timer = setTimeout(poll,2000);
      });
    };
    window.SteamClient.Downloads = {
      RegisterForDownloadItems:listener => {
        if (typeof listener !== 'function' || listeners.size >= 8) throw Error('Invalid download listener');
        listeners.add(listener); poll();
        return {unregister() {listeners.delete(listener); if (!listeners.size) close();}};
      },
      FrameyQueueDownloads:async appids => {
        if (closed || !available || !listeners.size) throw Error('Steam download list is unavailable');
        const value = await request('queue',[appids,revision],false,'framey:downloads');
        clearTimeout(timer); poll();
        return value;
      },
    };
    addEventListener('pagehide',() => {closed = true; listeners.clear(); close();});
  }
  DFL.DialogButton.render = () => ({type: DFL.DialogButton});
  const toaster = {toast: ({title, body, subtext, icon, logo, duration, showToast=true, onClick}={}) => {
    const data = {title, body, subtext, icon, logo};
    if (!showToast) return {data, dismiss(){}};
    const item = document.createElement('section');
    item.setAttribute('role','status');
    const roots = [];
    const addContent = (tag, value) => {
      if (value === null || value === undefined || value === false) return;
      const node = document.createElement(tag);
      if (R.isValidElement(value) || Array.isArray(value)) {
        const root = window.ReactDOM.createRoot(node);
        roots.push(root);
        root.render(value);
      } else if (typeof value === 'string' || typeof value === 'number') {
        node.textContent = String(value);
      } else return;
      item.append(node);
    };
    addContent('span', logo);
    addContent('span', icon);
    addContent('strong', title || 'Plugin notice');
    addContent('p', body);
    addContent('small', subtext);
    const close = document.createElement('button'); close.type='button'; close.textContent='Dismiss';
    let dismissed = false;
    const dismiss = () => {
      if (dismissed) return;
      dismissed = true;
      clearTimeout(timer);
      for (const root of roots) root.unmount();
      item.remove();
    };
    close.onclick=dismiss; item.append(close);
    if (typeof onClick === 'function') {
      const open = document.createElement('button'); open.type='button'; open.textContent='Open';
      open.onclick=()=>{onClick(); dismiss();}; item.append(open);
    }
    toastRoot.append(item);
    const timer = setTimeout(dismiss, Math.min(30000,Math.max(3000,Number(duration)||5000)));
    return {data,dismiss};
  }};
  class PanelBoundary extends R.Component {
    constructor(props) { super(props); this.state = {failure:null}; }
    static getDerivedStateFromError(failure) { return {failure}; }
    render() { return this.state.failure ? R.createElement('p', null,
      `This Decky panel is not compatible with Framey: ${this.state.failure.message}`) : this.props.children; }
  }
  function PluginSurface({plugin}) {
    const [view, setView] = R.useState(plugin.content ? 'panel' : 'settings');
    const [route, setRoute] = R.useState(currentRoute);
    R.useEffect(() => {routeListeners.add(setRoute); return () => routeListeners.delete(setRoute);}, []);
    const [running, setRunning] = R.useState(null);
    const runningRef = R.useRef(false);
    const [message, setMessage] = R.useState('');
    const actions = Array.isArray(plugin.frameyQuickActions) ? plugin.frameyQuickActions
      .filter(action => action && typeof action.label === 'string' && action.label.length <= 80 &&
        typeof action.onClick === 'function').slice(0, 8) : [];
    async function runAction(action, index) {
      // React state may not render between two controller clicks. Lock before
      // awaiting a backend action so one tap cannot start a second mutation.
      if (runningRef.current) return;
      runningRef.current = true;
      setRunning(index); setMessage(`${action.label}…`);
      try {
        const result = await action.onClick();
        setMessage(typeof result === 'string' && result.length < 200 ? result : `${action.label} done`);
      } catch (failure) { setMessage(`${action.label} failed: ${failure.message || failure}`); }
      finally { runningRef.current = false; setRunning(null); }
    }
    return R.createElement(R.Fragment, null,
      plugin.titleView && R.createElement('header', null, plugin.titleView),
      route && R.createElement('button', {type:'button', onClick:()=>navigate(null)}, 'Back to plugin'),
      plugin.content && plugin.settings && R.createElement('nav', {'aria-label':'Plugin views'},
        R.createElement('button', {type:'button', 'aria-current':view === 'panel' ? 'page' : undefined,
          onClick:()=>setView('panel')}, 'Panel'),
        R.createElement('button', {type:'button', 'aria-current':view === 'settings' ? 'page' : undefined,
          onClick:()=>setView('settings')}, 'Settings')),
      actions.length > 0 && R.createElement('section', {'aria-label':'Plugin quick actions'},
        R.createElement('h2', null, 'Quick actions'),
        ...actions.map((action, index) => R.createElement('button', {key:index, type:'button',
          disabled:running !== null, onClick:()=>runAction(action,index)}, action.label))),
      message && R.createElement('p', {role:'status'}, message),
      R.createElement('div', null, route ? (typeof activeRoute(route)?.component === 'function' ?
        R.createElement(activeRoute(route).component) : activeRoute(route)?.component) :
        (view === 'settings' ? plugin.settings : plugin.content)));
  }
  window.__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit = {
    connect: (version, name) => ({
      _version: Math.min(version, 2),
      call: (method, ...args) => ask(method, args),
      callable: method => (...args) => ask(method, args),
      addEventListener:addPluginEvent, removeEventListener:removePluginEvent,
      routerHook, toaster,
      fetchNoCors: () => Promise.reject(Error('Decky proxy fetch is unavailable in Framey')),
      executeInTab: () => Promise.reject(Error('Steam tab injection is unavailable in Framey')),
      injectCssIntoTab: () => Promise.reject(Error('Steam tab injection is unavailable in Framey')),
      removeCssFromTab: () => Promise.reject(Error('Steam tab injection is unavailable in Framey')),
      getExternalResourceURL: () => null,
      useQuickAccessVisible: () => true,
    }),
  };
  const legacyServerAPI = {
    routerHook, toaster,
    callPluginMethod: (method, kwargs={}) => {
      if (!kwargs || typeof kwargs !== 'object' || Array.isArray(kwargs))
        return Promise.resolve({success:false, result:'Legacy plugin arguments must be an object'});
      // Decky's legacy route takes keyword arguments and returns this envelope.
      return ask(method, [kwargs], true).catch(failure=>({success:false, result:String(failure.message || failure)}));
    },
    fetchNoCors: () => Promise.reject(Error('Decky proxy fetch is unavailable in Framey')),
  };
  function projectApps(rows, limit) {
    if (!Array.isArray(rows) || rows.length > limit) throw Error('Invalid Steam app overview');
    return rows.map(row => {
      if (!Array.isArray(row) || (row.length !== 8 && row.length !== 9) || !Number.isSafeInteger(row[0]) || row[0] <= 0 ||
          typeof row[1] !== 'string' || row[1].length > 2048 ||
          (row[2] != null && typeof row[2] !== 'string') || !Number.isSafeInteger(row[3]) ||
          typeof row[4] !== 'string' || !/^\d{1,20}$/.test(row[4]) ||
          row.slice(5,8).some(value=>value != null && (!Number.isFinite(value) || value < 0)) ||
          (row.length === 9 && row[8] !== null && typeof row[8] !== 'boolean'))
        throw Error('Invalid Steam app overview');
      const [appid,display_name,sort_as,app_type,gameid,
        minutes_playtime_forever,minutes_playtime_last_two_weeks,rt_last_time_played] = row;
      return {appid,display_name,sort_as,app_type,gameid,
        minutes_playtime_forever,minutes_playtime_last_two_weeks,rt_last_time_played,
        // null means Steam supplied no installed boolean, not false. Keep the
        // detached metadata object for legacy readers; never copy paths/client IDs.
        // Older/running snapshots omit this field and must not erase library data.
        ...(row.length === 9 ? {local_per_client_data:row[8] === null ? {} : {installed:row[8]}} : {})};
    });
  }
  function setLibrarySnapshot(snapshot) {
    // These are detached plugin-local values. Patching an overview or its Map
    // must never mutate Steam's library. Live MobX observations are unsupported.
    if (!snapshot || !Array.isArray(snapshot.apps) || snapshot.apps.length > 10000 ||
        !Array.isArray(snapshot.gameIds) || snapshot.gameIds.length > 10000 ||
        (snapshot.steamId != null && (typeof snapshot.steamId !== 'string' || !/^\d{17}$/.test(snapshot.steamId))))
      throw Error('Invalid Steam library snapshot');
    const apps = projectApps(snapshot.apps, 10000);
    const map = new Map(apps.map(app=>[app.appid,app]));
    if (map.size !== apps.length || snapshot.gameIds.some(id=>!Number.isSafeInteger(id) || !map.has(id)))
      throw Error('Invalid Steam game collection');
    window.appStore = {allApps:apps, m_mapApps:map,
      GetAppOverviewByAppID:id=>map.get(Number(id)),
      GetAppOverviewByGameID:id=>apps.find(app=>app.gameid === String(id)),
      GetVerticalCapsuleURLForApp:app=>runningArtwork.get(Number(app?.appid))?.[0] || '',
      GetCustomVerticalCapsuleURLs:app=>[...(runningArtwork.get(Number(app?.appid))?.[1] || [])],
    };
    window.collectionStore = {allGamesCollection:{allApps:snapshot.gameIds.map(id=>map.get(id))}};
    window.App = snapshot.steamId ? {m_CurrentUser:{strSteamID:snapshot.steamId}} : undefined;
  }
  function setRunningSnapshot(data) {
    if (!data || !Array.isArray(data.runningIds) || data.runningIds.length > 64 ||
        !Array.isArray(data.events) || data.events.length > 64 ||
        !Array.isArray(data.artwork) || data.artwork.length > 65 ||
        !Number.isSafeInteger(data.cursor) || data.cursor < 0 || typeof data.lifetimeAvailable !== 'boolean')
      throw Error('Invalid Steam running snapshot');
    const apps = projectApps(data.apps, 65), map = new Map(apps.map(app=>[app.appid,app]));
    if (map.size !== apps.length || new Set(data.runningIds).size !== data.runningIds.length ||
        data.runningIds.some(id=>!Number.isSafeInteger(id) || !map.has(id)) ||
        (data.mainAppId !== null && (!Number.isSafeInteger(data.mainAppId) || !map.has(data.mainAppId))))
      throw Error('Invalid Steam running apps');
    let sequence = 0;
    const publicArt = value => typeof value === 'string' && value.length <= 2048 &&
      /^https:\/\/(?:[a-z0-9-]+\.)*steamstatic\.com\/steam\/apps\/[^?#\s\\]+$/.test(value);
    const artwork = new Map();
    for (const row of data.artwork) {
      if (!Array.isArray(row) || row.length !== 3 || !map.has(row[0]) || artwork.has(row[0]) ||
          (row[1] !== null && !publicArt(row[1])) || !Array.isArray(row[2]) || row[2].length > 8 ||
          row[2].some(url=>!publicArt(url))) throw Error('Invalid Steam public artwork');
      artwork.set(row[0],[row[1],[...row[2]]]);
    }
    for (const event of data.events) {
      if (!Number.isSafeInteger(event?.sequence) || event.sequence <= sequence || event.sequence > data.cursor ||
          !Number.isSafeInteger(event.unAppID) || event.unAppID <= 0 || typeof event.bRunning !== 'boolean')
        throw Error('Invalid Steam lifetime event');
      sequence = event.sequence;
    }
    // Update detached stores before callbacks read Router.RunningApps.
    runningApps = Object.freeze(data.runningIds.map(id=>map.get(id)));
    mainRunningApp = data.mainAppId === null ? undefined : map.get(data.mainAppId);
    runningAvailable = true;
    runningArtwork = artwork;
    if (window.appStore) for (const app of apps) {
      const existing = window.appStore.m_mapApps.get(app.appid);
      if (existing) Object.assign(existing,app);
      else {window.appStore.m_mapApps.set(app.appid,app);window.appStore.allApps.push(app);}
    }
    const previous = runningCursor;
    runningCursor = data.cursor;
    for (const event of data.events) if (event.sequence > previous)
      for (const listener of runningListeners)
        Promise.resolve().then(()=>runningListeners.has(listener) && listener({unAppID:event.unAppID,bRunning:event.bRunning}))
          .catch(failure=>console.warn('Steam lifetime listener failed',failure.message));
  }
  function refreshRunning() {
    if (runningClosed) return Promise.resolve();
    if (runningRequest) return runningRequest;
    runningRequest = request('running',[runningCursor],false,'framey:running')
      .then(data=>{if (!runningClosed) setRunningSnapshot(data);})
      .catch(failure=>{
        runningAvailable = false;
        runningApps = Object.freeze([]); mainRunningApp = undefined; runningArtwork = new Map();
        console.warn('Framey Steam running context unavailable',failure.message);
      }).finally(()=>{
        runningRequest = null;
        if (!runningClosed) runningTimer = setTimeout(refreshRunning,2000);
      });
    return runningRequest;
  }
  addEventListener('pagehide',()=>{
    runningClosed = true; clearTimeout(runningTimer); runningListeners.clear();
    parent.postMessage({type:'framey:running:close',session:cacheSession},'*');
  });
  async function start() {
    try {
      await waitForSeed();
      const bundleNode = document.getElementById('framey-bundle');
      const bytes = Uint8Array.from(atob(bundleNode.textContent), c=>c.charCodeAt(0));
      const bundleText = new TextDecoder().decode(bytes);
      // Only panels referencing library globals need the extra read. A failed
      // read leaves them unavailable rather than fabricating an empty library.
      if (/\b(?:appStore|collectionStore|m_CurrentUser)\b/.test(bundleText)) {
        try {setLibrarySnapshot(await request('GetLibrarySnapshot',[],false,'framey:steam'));}
        catch (failure) {console.warn('Framey Steam library unavailable', failure.message);}
      }
      if (/\b(?:RunningApps|MainRunningApp|RegisterForAppLifetimeNotifications)\b/.test(bundleText))
        await refreshRunning();
      // Old Decky builds are expressions returning the initializer, rather than
      // ES modules. A module wrapper preserves the sandbox and avoids eval.
      const legacy = /^\s*\(function\s*\(/.test(bundleText);
      let module;
      if (bundleNode.dataset.module && !legacy) {
        // A hierarchical URL lets official Vite chunks resolve relative imports.
        module = await import(new URL(bundleNode.dataset.module, location.href).href);
      } else {
        const url = URL.createObjectURL(new Blob(legacy ?
          ['const __frameyLegacy =\n', bytes, '\nexport default __frameyLegacy;'] : [bytes], {type:'text/javascript'}));
        try { module = await import(url); } finally { URL.revokeObjectURL(url); }
      }
      if (typeof module.default !== 'function') throw Error('The Decky frontend has no plugin entry point');
      plugin = await module.default(legacyServerAPI);
      if (legacy && plugin?.title && !plugin.titleView) plugin.titleView = plugin.title;
      if (!plugin?.content && !plugin?.settings) throw Error('The Decky plugin has no panel to display');
      window.ReactDOM.createRoot(root).render(R.createElement(PanelBoundary, null,
        R.createElement(PluginSurface, {plugin})));
      parent.postMessage({type:'framey:ready', session:cacheSession}, '*');
    } catch (failure) {
      error.textContent = `This Decky panel is not compatible with Framey: ${failure.message}`;
      parent.postMessage({type:'framey:error', session:cacheSession,
        message:failure.message}, '*');
    }
  }
  start();
})();
