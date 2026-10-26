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
  const pending = new Map();
  const routes = new Map();
  const routeListeners = new Set();
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
  let acceptSeed;
  const seeded = new Promise(resolve => {acceptSeed = resolve;});
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
  setTimeout(() => {acceptSeed?.(); acceptSeed = null;}, 1000); // Open if storage is unavailable.

  function request(method, args, legacy=false, type='framey:call') {
    if (!/^[A-Za-z][A-Za-z0-9_]{0,63}$/.test(method)) return Promise.reject(Error('Invalid backend method'));
    const id = ++nextId;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { pending.delete(id); reject(Error('Decky backend timed out')); }, 30000);
      pending.set(id, {resolve, reject, timer});
      parent.postMessage({type, id, method, args, legacy, session:cacheSession}, '*');
    });
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
    if (event.source === parent && event.data?.type === 'framey:cache:seed' &&
        event.data.session === cacheSession && acceptSeed) {
      const entries = event.data.entries;
      if (entries && typeof entries === 'object' && !Array.isArray(entries)) {
        for (const [key, value] of Object.entries(entries))
          if (key.length <= 256 && typeof value === 'string' && value.length <= 65536)
            cache.set(key, value);
      }
      acceptSeed(); acceptSeed = null;
      return;
    }
    if (event.source !== parent || !event.data || event.data.type !== 'framey:reply') return;
    const item = pending.get(event.data.id);
    if (!item) return;
    pending.delete(event.data.id); clearTimeout(item.timer);
    if (event.data.error) item.reject(Error(event.data.error)); else item.resolve(event.data.result);
  });
  addEventListener('unload', () => {
    eventClosed = true; clearTimeout(eventTimer);
    try { plugin?.onDismount?.(); } catch (_) {}
    // Parent tears down the remote session on close; CEF also expires it after 15s.
    parent.postMessage({type:'framey:events:close', session:cacheSession}, '*');
  });
  addEventListener('pointerup', event => {
    if (event.isTrusted) parent.postMessage({type:'framey:input'}, '*');
  }, {passive:true});

  const passthrough = tag => ({children, ...props}) => R.createElement(tag, props, children);
  const Field = ({label, description, children}) => R.createElement('label', null,
    R.createElement('strong', null, label), description && R.createElement('small', null, description), children);
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
  const ProgressBar = ({nProgress=0, value, max=100}) => R.createElement('progress', {
    value:Math.max(0,Math.min(max,Number(value ?? nProgress)||0)), max});
  const MenuItem = ({children, disabled, bDisabled, onClick, onSelected}) =>
    R.createElement('button', {type:'button',disabled:!!(disabled || bDisabled),
      onClick:event=>{if(!disabled && !bDisabled)(onClick || onSelected)?.(event);}}, children);
  const ConfirmModal = ({strTitle, strOKButtonText, onOK, children}) => R.createElement('section', null,
    R.createElement('h2', null, strTitle), children,
    R.createElement('button', {type:'button', onClick:()=>{onOK?.(); closeModal();}}, strOKButtonText || 'Close'));
  const modalRoot = window.ReactDOM.createRoot(document.getElementById('framey-modal'));
  const closeModal = () => modalRoot.render(null);
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
  function navigate(path) {
    if (path !== null && !localPath(path)) return false;
    const match = path === null ? null : activeRoute(path);
    if (path !== null && !match) return false;
    currentRoute = path;
    currentParams = match?.params || {};
    for (const listener of routeListeners) listener(path);
    return true;
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
  const showModal = element => {
    modalRoot.render(R.createElement('section', null,
      R.createElement('button', {type:'button',onClick:closeModal}, 'Close'), element));
    return {Close:closeModal};
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
    Focusable: passthrough('div'), ScrollPanel: passthrough('div'), ScrollPanelGroup: passthrough('div'),
    DialogButton: passthrough('button'), DialogButtonPrimary: passthrough('button'), ConfirmModal,
    DialogButtonSecondary: passthrough('button'), Button: ButtonItem, GamepadButton: passthrough('button'),
    Toggle: ToggleField, Spinner, SteamSpinner:Spinner, Tabs, SidebarNavigation,
    SuspensefulImage:({alt='', ...props})=>R.createElement('img', {...props, alt}),
    Marquee:passthrough('span'), DialogBody:passthrough('div'), DialogBodyText:passthrough('p'),
    DialogHeader:passthrough('h2'), DialogSubHeader:passthrough('h3'), DialogFooter:passthrough('footer'),
    DialogLabel:passthrough('label'), DialogControlsSection:passthrough('section'),
    DialogControlsSectionHeader:passthrough('h3'), ModalRoot:passthrough('section'),
    ModalPosition:passthrough('div'),
    Menu:passthrough('div'), MenuGroup:passthrough('section'), MenuItem,
    ProgressBar, ProgressBarWithInfo:ProgressBar,
    gamepadDialogClasses:{}, quickAccessMenuClasses:{}, gamepadTabbedPageClasses:{},
    gamepadSliderClasses:{}, gamepadContextMenuClasses:{}, scrollPanelClasses:{},
    quickAccessControlsClasses:{}, mainMenuAppRunningClasses:{}, libraryAssetImageClasses:{},
    joinClassNames:(...names)=>names.filter(Boolean).join(' '),
    sleep:ms=>new Promise(resolve=>setTimeout(resolve,Math.max(0,Number(ms)||0))),
    staticClasses: {Title:'framey-title'},
    Navigation: {Navigate:navigate, NavigateBack:()=>navigate(null), CloseSideMenus:()=>navigate(null),
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
    findSP:()=>null, fakeRenderComponent:()=>null,
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
      if (!Array.isArray(row) || row.length !== 8 || !Number.isSafeInteger(row[0]) || row[0] <= 0 ||
          typeof row[1] !== 'string' || row[1].length > 2048 ||
          (row[2] != null && typeof row[2] !== 'string') || !Number.isSafeInteger(row[3]) ||
          typeof row[4] !== 'string' || !/^\d{1,20}$/.test(row[4]) ||
          row.slice(5).some(value=>value != null && (!Number.isFinite(value) || value < 0)))
        throw Error('Invalid Steam app overview');
      const [appid,display_name,sort_as,app_type,gameid,
        minutes_playtime_forever,minutes_playtime_last_two_weeks,rt_last_time_played] = row;
      return {appid,display_name,sort_as,app_type,gameid,
        minutes_playtime_forever,minutes_playtime_last_two_weeks,rt_last_time_played};
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
      await seeded;
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
      parent.postMessage({type:'framey:ready'}, '*');
    } catch (failure) {
      error.textContent = `This Decky panel is not compatible with Framey: ${failure.message}`;
      parent.postMessage({type:'framey:error', message:failure.message}, '*');
    }
  }
  start();
})();
