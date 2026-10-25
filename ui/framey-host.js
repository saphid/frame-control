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
  // Steam normally fills these token maps. Official plugins can safely use
  // their own fallback strings when the isolated panel has no Steam tokens.
  window.LocalizationManager = {m_rgLocalesToUse:[navigator.language || 'en'],
    m_mapTokens:new Map(), m_mapFallbackTokens:new Map()};
  const root = document.getElementById('framey-root');
  const error = document.getElementById('framey-error');
  const toastRoot = document.getElementById('framey-toasts');
  const pending = new Map();
  const routes = new Map();
  const routeListeners = new Set();
  let currentRoute = null;
  let nextId = 0;
  let plugin;
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
  parent.postMessage({type:'framey:cache:init', session:cacheSession}, '*');
  setTimeout(() => {acceptSeed?.(); acceptSeed = null;}, 1000); // Open if storage is unavailable.

  function ask(method, args) {
    if (!/^[A-Za-z][A-Za-z0-9_]{0,63}$/.test(method)) return Promise.reject(Error('Invalid backend method'));
    const id = ++nextId;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { pending.delete(id); reject(Error('Decky backend timed out')); }, 30000);
      pending.set(id, {resolve, reject, timer});
      parent.postMessage({type:'framey:call', id, method, args}, '*');
    });
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
  addEventListener('unload', () => { try { plugin?.onDismount?.(); } catch (_) {} });
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
  const SliderField = ({label, description, value, min=0, max=100, step=1, disabled, showValue,
    valueSuffix='', onChange}) => R.createElement(Field, {label, description},
    R.createElement('input', {type:'range', value, min, max, step, disabled:!!disabled,
      'aria-label':typeof label==='string'?label:undefined,
      onChange:e=>{if(!disabled)onChange?.(Number(e.target.value));}}),
    showValue && R.createElement('span', null, String(value) + valueSuffix));
  const PanelSection = ({title, children}) => R.createElement('section', null,
    title && R.createElement('h2', null, title), children);
  const ConfirmModal = ({strTitle, strOKButtonText, onOK, children}) => R.createElement('section', null,
    R.createElement('h2', null, strTitle), children,
    R.createElement('button', {type:'button', onClick:()=>{onOK?.(); closeModal();}}, strOKButtonText || 'Close'));
  const modalRoot = window.ReactDOM.createRoot(document.getElementById('framey-modal'));
  const closeModal = () => modalRoot.render(null);
  function navigate(path) {
    if (path !== null && (!/^\/[A-Za-z0-9/_-]{1,120}$/.test(path) || !routes.has(path))) return false;
    currentRoute = path;
    for (const listener of routeListeners) listener(path);
    return true;
  }
  const routerHook = {
    addRoute(path, component) {
      if (!/^\/[A-Za-z0-9/_-]{1,120}$/.test(path) ||
          (typeof component !== 'function' && !R.isValidElement(component)))
        throw Error('Framey route needs a local path and React component');
      routes.set(path, component);
      return () => {routes.delete(path); if(currentRoute === path) navigate(null);};
    },
    removeRoute(path) {routes.delete(path); if(currentRoute === path) navigate(null);},
    // Steam routes and global components have no equivalent in the isolated panel.
    addPatch:()=>()=>{}, removePatch:()=>{}, addGlobalComponent:()=>{}, removeGlobalComponent:()=>{},
  };
  const DFL = window.DFL = {
    definePlugin: init => init,
    PanelSection, PanelSectionRow: passthrough('div'), Field, ToggleField, DropdownItem,
    Dropdown: DropdownItem, ButtonItem, DialogCheckbox, TextField, SliderField,
    Focusable: passthrough('div'), ScrollPanel: passthrough('div'), ScrollPanelGroup: passthrough('div'),
    DialogButton: passthrough('button'), DialogButtonPrimary: passthrough('button'), ConfirmModal,
    staticClasses: {Title:'framey-title'},
    Navigation: {Navigate:navigate, NavigateBack:()=>navigate(null),
      NavigateToExternalWeb: url => { if (/^https:\/\//.test(url)) window.open(url, '_blank', 'noopener'); }},
    showModal: element => modalRoot.render(R.createElement('section', null,
      R.createElement('button', {onClick:closeModal}, 'Close'), element)),
    // Steam app, library, and store patches have no target inside this panel.
    afterPatch: () => () => {}, createReactTreePatcher: () => () => {},
    findInReactTree: () => null, findModuleExport: () => null,
    appDetailsClasses: {}, appDetailsHeaderClasses: {},
    useParams: () => ({}),
  };
  DFL.DialogButton.render = () => ({type: DFL.DialogButton});
  const toaster = {toast: ({title, body, duration, showToast=true, onClick}={}) => {
    const data = {title, body};
    if (!showToast) return {data, dismiss(){}};
    const item = document.createElement('section');
    item.setAttribute('role','status');
    const heading = document.createElement('strong'); heading.textContent = String(title || 'Plugin notice');
    const detail = document.createElement('p'); detail.textContent = String(body || '');
    const close = document.createElement('button'); close.type='button'; close.textContent='Dismiss';
    const dismiss = () => {item.remove(); clearTimeout(timer);};
    close.onclick=dismiss; item.append(heading, detail, close);
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
    const [message, setMessage] = R.useState('');
    const actions = Array.isArray(plugin.frameyQuickActions) ? plugin.frameyQuickActions.slice(0, 8)
      .filter(action => action && typeof action.label === 'string' && action.label.length <= 80 &&
        typeof action.onClick === 'function') : [];
    async function runAction(action, index) {
      if (running !== null) return;
      setRunning(index); setMessage(`${action.label}…`);
      try {
        const result = await action.onClick();
        setMessage(typeof result === 'string' && result.length < 200 ? result : `${action.label} done`);
      } catch (failure) { setMessage(`${action.label} failed: ${failure.message || failure}`); }
      finally { setRunning(null); }
    }
    return R.createElement(R.Fragment, null,
      plugin.titleView && R.createElement('header', null, plugin.titleView),
      route && R.createElement('button', {type:'button', onClick:()=>navigate(null)}, 'Back to plugin'),
      plugin.settings && R.createElement('nav', {'aria-label':'Plugin views'},
        R.createElement('button', {type:'button', 'aria-current':view === 'panel' ? 'page' : undefined,
          onClick:()=>setView('panel')}, 'Panel'),
        R.createElement('button', {type:'button', 'aria-current':view === 'settings' ? 'page' : undefined,
          onClick:()=>setView('settings')}, 'Settings')),
      actions.length > 0 && R.createElement('section', {'aria-label':'Plugin quick actions'},
        R.createElement('h2', null, 'Quick actions'),
        ...actions.map((action, index) => R.createElement('button', {key:index, type:'button',
          disabled:running !== null, onClick:()=>runAction(action,index)}, action.label))),
      message && R.createElement('p', {role:'status'}, message),
      R.createElement('div', null, route ? (typeof routes.get(route) === 'function' ?
        R.createElement(routes.get(route)) : routes.get(route)) :
        (view === 'settings' ? plugin.settings : plugin.content)));
  }
  window.__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit = {
    connect: (version, name) => ({
      _version: Math.min(version, 2),
      call: (method, ...args) => ask(method, args),
      callable: method => (...args) => ask(method, args),
      addEventListener: () => {}, removeEventListener: () => {},
      routerHook, toaster,
      fetchNoCors: () => Promise.reject(Error('Decky proxy fetch is unavailable in Framey')),
      executeInTab: () => Promise.reject(Error('Steam tab injection is unavailable in Framey')),
      injectCssIntoTab: () => Promise.reject(Error('Steam tab injection is unavailable in Framey')),
      removeCssFromTab: () => Promise.reject(Error('Steam tab injection is unavailable in Framey')),
      getExternalResourceURL: () => null,
      useQuickAccessVisible: () => true,
    }),
  };
  async function start() {
    try {
      await seeded;
      const bytes = Uint8Array.from(atob(document.getElementById('framey-bundle').textContent), c=>c.charCodeAt(0));
      const url = URL.createObjectURL(new Blob([bytes], {type:'text/javascript'}));
      let module;
      try { module = await import(url); } finally { URL.revokeObjectURL(url); }
      if (typeof module.default !== 'function') throw Error('The Decky frontend has no plugin entry point');
      plugin = await module.default();
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
