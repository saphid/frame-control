/* Framey panel compatibility layer. The iframe has an opaque origin and no UI key. */
(() => {
  'use strict';
  const R = window.SP_REACT = window.React;
  window.SP_REACTDOM = window.ReactDOM;
  window.LocalizationManager = {m_rgLocalesToUse:[navigator.language || 'en']};
  const root = document.getElementById('framey-root');
  const error = document.getElementById('framey-error');
  const pending = new Map();
  let nextId = 0;
  let plugin;

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
  const ToggleField = ({label, description, checked, onChange}) => R.createElement(Field, {label, description},
    R.createElement('input', {type:'checkbox', checked:!!checked, onChange:e=>onChange?.(e.target.checked)}));
  const DropdownItem = ({label, description, rgOptions=[], selectedOption, onChange}) => R.createElement(Field, {label, description},
    R.createElement('select', {value:String(selectedOption ?? ''), onChange:e=>onChange?.(rgOptions.find(x=>String(x.data)===e.target.value))},
      rgOptions.map(x=>R.createElement('option', {key:String(x.data), value:String(x.data)}, x.label))));
  const ButtonItem = ({label, children, onClick}) => R.createElement(Field, {label},
    R.createElement('button', {type:'button', onClick}, children || label));
  const PanelSection = ({title, children}) => R.createElement('section', null,
    title && R.createElement('h2', null, title), children);
  const ConfirmModal = ({strTitle, strOKButtonText, onOK, children}) => R.createElement('section', null,
    R.createElement('h2', null, strTitle), children,
    R.createElement('button', {type:'button', onClick:()=>{onOK?.(); closeModal();}}, strOKButtonText || 'Close'));
  const modalRoot = window.ReactDOM.createRoot(document.getElementById('framey-modal'));
  const closeModal = () => modalRoot.render(null);
  const DFL = window.DFL = {
    definePlugin: init => init,
    PanelSection, PanelSectionRow: passthrough('div'), Field, ToggleField, DropdownItem, ButtonItem,
    Focusable: passthrough('div'), ScrollPanel: passthrough('div'), ScrollPanelGroup: passthrough('div'),
    DialogButton: passthrough('button'), ConfirmModal,
    staticClasses: {Title:'framey-title'},
    Navigation: {NavigateToExternalWeb: url => { if (/^https:\/\//.test(url)) window.open(url, '_blank', 'noopener'); }},
    showModal: element => modalRoot.render(R.createElement('section', null,
      R.createElement('button', {onClick:closeModal}, 'Close'), element)),
    // Steam app, library, and store patches have no target inside this panel.
    afterPatch: () => () => {}, createReactTreePatcher: () => () => {},
    findInReactTree: () => null, findModuleExport: () => null,
    appDetailsClasses: {}, appDetailsHeaderClasses: {},
    useParams: () => ({}),
  };
  DFL.DialogButton.render = () => ({type: DFL.DialogButton});
  const noRoute = {addPatch:()=>()=>{}, removePatch:()=>{}, addGlobalComponent:()=>{}, removeGlobalComponent:()=>{}};
  const toaster = {toast: ({title, body}) => { error.textContent = [title, body].filter(Boolean).join(': '); }};
  class PanelBoundary extends R.Component {
    constructor(props) { super(props); this.state = {failure:null}; }
    static getDerivedStateFromError(failure) { return {failure}; }
    render() { return this.state.failure ? R.createElement('p', null,
      `This Decky panel is not compatible with Framey: ${this.state.failure.message}`) : this.props.children; }
  }
  window.__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit = {
    connect: (version, name) => ({
      _version: Math.min(version, 2),
      call: (method, ...args) => ask(method, args),
      callable: method => (...args) => ask(method, args),
      addEventListener: () => {}, removeEventListener: () => {},
      routerHook:noRoute, toaster,
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
      const bytes = Uint8Array.from(atob(document.getElementById('framey-bundle').textContent), c=>c.charCodeAt(0));
      const url = URL.createObjectURL(new Blob([bytes], {type:'text/javascript'}));
      let module;
      try { module = await import(url); } finally { URL.revokeObjectURL(url); }
      if (typeof module.default !== 'function') throw Error('The Decky frontend has no plugin entry point');
      plugin = await module.default();
      if (!plugin?.content) throw Error('The Decky plugin has no panel to display');
      window.ReactDOM.createRoot(root).render(R.createElement(PanelBoundary, null, plugin.content));
      parent.postMessage({type:'framey:ready'}, '*');
    } catch (failure) {
      error.textContent = `This Decky panel is not compatible with Framey: ${failure.message}`;
      parent.postMessage({type:'framey:error', message:failure.message}, '*');
    }
  }
  start();
})();
