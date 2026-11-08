const manifest = {"name":"Framey Settings Sample"};
const API_VERSION = 2;
const internalAPIConnection = window.__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit;
if (!internalAPIConnection) {
    throw new Error('[@decky/api]: Failed to connect to the loader as as the loader API was not initialized. This is likely a bug in Decky Loader.');
}
let api;
try {
    api = internalAPIConnection.connect(API_VERSION, manifest.name);
}
catch {
    api = internalAPIConnection.connect(1, manifest.name);
    console.warn(`[@decky/api] Requested API version ${API_VERSION} but the running loader only supports version 1. Some features may not work.`);
}
if (api._version != API_VERSION) {
    console.warn(`[@decky/api] Requested API version ${API_VERSION} but the running loader only supports version ${api._version}. Some features may not work.`);
}
const callable = api.callable;
const routerHook = api.routerHook;
const toaster = api.toaster;
const definePlugin = (fn) => {
    return (...args) => {
        return fn(...args);
    };
};

const getSetting = callable('get_setting');
const setSetting = callable('set_setting');
async function readEnabled() {
    const value = await getSetting('enabled', false);
    if (typeof value !== 'boolean')
        throw new Error('Backend returned an invalid setting value.');
    return value;
}
function Content() {
    const [enabled, setEnabled] = SP_REACT.useState(false);
    const [busy, setBusy] = SP_REACT.useState(true);
    const [message, setMessage] = SP_REACT.useState('Loading setting…');
    const pending = SP_REACT.useRef(false);
    const resetDialog = SP_REACT.useRef(null);
    const readReady = SP_REACT.useRef(false);
    const active = SP_REACT.useRef(true);
    const requestSequence = SP_REACT.useRef(0);
    async function refresh() {
        if (!active.current || pending.current)
            return;
        const request = ++requestSequence.current;
        const isCurrent = () => active.current && request === requestSequence.current;
        pending.current = true;
        readReady.current = false;
        setBusy(true);
        try {
            const value = await readEnabled();
            if (!isCurrent())
                return;
            readReady.current = true;
            setEnabled(value);
            setMessage(`Saved setting: ${value ? 'on' : 'off'}`);
        }
        catch (error) {
            if (isCurrent())
                setMessage(`Could not read setting: ${String(error)}. Reload saved setting before changing it.`);
        }
        finally {
            if (isCurrent()) {
                pending.current = false;
                setBusy(false);
            }
        }
    }
    SP_REACT.useEffect(() => {
        active.current = true;
        void refresh();
        return () => {
            // Retire this view's callbacks, not a write already sent to the backend.
            // Advancing the sequence also protects a fresh effect setup/replay.
            active.current = false;
            requestSequence.current++;
            pending.current = false;
            readReady.current = false;
            resetDialog.current?.Close();
            resetDialog.current = null;
        };
    }, []);
    async function change(value) {
        // Two controller events can arrive before React redraws the disabled toggle.
        // Keep writes ordered so a late first reply cannot replace the final choice.
        if (!active.current || pending.current)
            return;
        if (!readReady.current)
            throw new Error('Reload saved setting before changing it.');
        const request = ++requestSequence.current;
        const isCurrent = () => active.current && request === requestSequence.current;
        pending.current = true;
        setBusy(true);
        try {
            const saved = await setSetting('enabled', value);
            if (!isCurrent())
                return;
            if (saved !== true)
                throw new Error('Backend did not acknowledge the saved setting.');
            setEnabled(value);
            setMessage(`Saved setting: ${value ? 'on' : 'off'}`);
            toaster.toast({ title: 'Framey sample',
                body: SP_JSX.jsxs("span", { children: ["Setting saved: ", SP_JSX.jsx("strong", { children: value ? 'on' : 'off' })] }) });
        }
        catch (error) {
            if (isCurrent()) {
                // A lost reply does not prove the backend failed to commit. Require a
                // fresh read rather than let another edit use the stale display value.
                readReady.current = false;
                const failure = new Error(`Could not confirm saved setting: ${String(error)}. Close any Reset dialog, then Reload saved setting before changing it.`);
                setMessage(failure.message);
                throw failure;
            }
            throw error;
        }
        finally {
            if (isCurrent()) {
                pending.current = false;
                setBusy(false);
            }
        }
    }
    function confirmReset() {
        if (!active.current || pending.current || !readReady.current || resetDialog.current)
            return;
        const dialog = DFL.showModal(SP_JSX.jsx(DFL.ConfirmModal, { strTitle: "Reset example setting?", strDescription: "This changes only the sample plugin's saved setting.", strOKButtonText: "Reset", strCancelButtonText: "Keep setting", onOK: () => change(false) }));
        resetDialog.current = dialog;
        void dialog.ClosedPromise.then(() => {
            if (resetDialog.current === dialog)
                resetDialog.current = null;
        });
    }
    return SP_JSX.jsxs(DFL.PanelSection, { title: "Framey settings sample", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ToggleField, { label: "Example setting", description: "Stored by the Decky Python backend", checked: enabled, disabled: busy || !readReady.current, onChange: (value) => { void change(value).catch(() => { }); } }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { disabled: busy, onClick: () => { void refresh(); }, children: "Reload saved setting" }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { disabled: busy || !readReady.current, onClick: confirmReset, children: "Reset example setting" }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { onClick: () => DFL.Navigation.Navigate('/framey-sample/details/saved-setting'), children: "About this setting" }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx("p", { role: "status", children: message }) })] });
}
function Details() {
    const { topic } = DFL.useParams();
    return SP_JSX.jsxs(DFL.PanelSection, { title: "Sample detail page", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsxs("p", { children: ["Topic: ", topic || 'overview'] }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx("p", { children: "The toggle is stored by this plugin's Decky backend in the user's settings directory." }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { onClick: () => DFL.Navigation.NavigateBack(), children: "Back to setting" }) })] });
}
var index = definePlugin(() => {
    routerHook.addRoute('/framey-sample/details/:topic?', Details);
    return Object.assign({
        name: 'Framey Settings Sample',
        icon: SP_JSX.jsx("span", { "aria-hidden": "true", children: "\u2699" }),
        content: SP_JSX.jsx(Content, {}),
        onDismount: () => routerHook.removeRoute('/framey-sample/details/:topic?'),
    }, {
        // Framey additions are ignored by Decky's own menu. Keep the main content
        // usable there too, while showing authors the extra VR settings view.
        settings: SP_JSX.jsx(Content, {}),
        frameyQuickActions: [{
                label: 'Read saved setting',
                onClick: async () => {
                    const enabled = await readEnabled();
                    return `Saved setting is ${enabled ? 'on' : 'off'}`;
                },
            }],
    });
});

export { index as default };
//# sourceMappingURL=index.js.map
